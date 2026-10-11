"""Local Ollama chat generation for grounded Poorvika responses."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

import requests

from app.config import settings

logger = logging.getLogger("shopai.services.ollama")
HTTP = requests.Session()


class SuggestionGroundingError(ValueError):
    """Generated question contains a factual value assigned to the wrong row."""


def _validate_listing_fact_associations(questions, product):
    """Keep numeric/specification facts attached to the model or variant named.

    This deliberately validates measurable claims with explicit model references;
    it does not try to infer every semantic statement in natural language.
    """
    rows = [row for row in product.get("products", []) if isinstance(row, dict)]
    if not rows:
        return
    code_pattern = re.compile(r"\b[A-Z]{1,4}\d{1,4}[A-Z]?\b", re.I)
    fact_pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:₹\s*\d+(?:,\d{3})*(?:\.\d+)?|INR\s*\d+(?:,\d{3})*(?:\.\d+)?|"
        r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:GB|TB|MB|mAh|MP|Hz|GHz|MHz|W|V|mm|cm|inch(?:es)?|\"|years?|months?|G)\b)",
        re.I,
    )
    price_pattern = re.compile(r"\b(?:price|priced|cost|costs)\b[^?]{0,24}?(\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
    codes_by_row = []
    for row in rows:
        identity = " ".join(str(row.get(key) or "") for key in ("name", "brand", "model", "id"))
        codes_by_row.append(set(code.upper() for code in code_pattern.findall(identity)))

    for question in questions:
        codes = [(match.group().upper(), match.start(), match.end()) for match in code_pattern.finditer(question)]
        facts = [(fact.start(), fact.group(), False) for fact in fact_pattern.finditer(question)]
        facts.extend((fact.start(1), fact.group(1), True) for fact in price_pattern.finditer(question))
        for fact_start, fact_text, is_price in facts:
            if not codes:
                continue
            code, _, _ = min(codes, key=lambda item: min(abs(fact_start - item[1]), abs(fact_start - item[2])))
            related = [row for row, row_codes in zip(rows, codes_by_row) if code in row_codes]
            if not related:
                continue
            currency_amount = re.search(r"(?:₹|INR)\s*(\d+(?:,\d{3})*(?:\.\d+)?)", fact_text, re.I)
            price_amount = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", fact_text) if is_price else None
            if currency_amount or price_amount:
                amount = Decimal((currency_amount or price_amount).group(1 if currency_amount else 0).replace(",", ""))
                supported = any(row.get("price") is not None and Decimal(str(row["price"])) == amount for row in related)
            else:
                normalized_fact = re.sub(r"\s+", "", fact_text).casefold().replace(",", "")
                supported = any(
                    normalized_fact in re.sub(r"\s+", "", json.dumps(row, ensure_ascii=False)).casefold().replace(",", "")
                    for row in related
                )
            if not supported:
                logger.warning("Suggestion rejected: product-fact association model=%s fact=%s", code, fact_text)
                raise SuggestionGroundingError("Generated question associates an unsupported fact with a product")


def validate_suggestion_claims(questions, product):
    """Reject unsupported features asserted in owned/causal clauses of questions."""
    def words(text):
        return {word.rstrip('s') for word in re.findall(r'[a-z]+', text.lower())}
    vocabulary = words(json.dumps(product, ensure_ascii=False))
    if vocabulary.intersection({'chipset', 'cpu'}):
        vocabulary.add('processor')
    neutral = words('the a an and or its their this that with of for to in on by has have is are as well material feature specification capability')
    for question in questions:
        clauses = re.findall(r'(?:due to|because of|considering|with)\s+(?:its|their)\s+([^?.;]+)', question, re.I)
        for clause in clauses:
            unsupported = words(clause) - vocabulary - neutral
            if unsupported:
                logger.warning('Suggestion rejected: unsupported asserted feature words=%s', sorted(unsupported))
                raise SuggestionGroundingError('Generated suggestion asserts an unsupported feature')

SYSTEM_PROMPT = (
    "Use only catalog data. Answer in one concise sentence with product name, exact INR price, "
    "and stock status. Use ₹ before the exact catalog price; never change its currency or value. "
    "Do not invent or infer product details. If the catalog context contains no products, say that "
    "there are no matching catalog results and invite the customer to broaden the search."
)


class OllamaService:
    """Generate a final natural-language answer with the configured local model."""

    def __init__(self) -> None:
        self.url = settings.OLLAMA_API_URL
        self.model = settings.OLLAMA_MODEL

    def generate(self, message: str, context: Dict[str, Any], timings: Dict[str, Any] | None = None) -> str:
        logger.info("OLLAMA request: model=%s", self.model)
        started = time.perf_counter()
        if timings is not None:
            timings["ollama_call_count"] = timings.get("ollama_call_count", 0) + 1
            timings["ollama_start"] = datetime.now(timezone.utc).isoformat()
        # Serialize only the already-filtered rows returned by PostgreSQL. This
        # is compact and avoids Python's verbose dict representation in prompts.
        information = context.get("suggestion_information") is True
        system_prompt = (
            "Answer the customer's product question concisely using only the supplied catalog "
            "name, INR price, stock and specifications. Cite relevant supplied field values "
            "without inventing advertised benefits, benchmark results or real-world performance. If the requested "
            "detail is not supplied, say it is unavailable. Evaluate compatibility against the "
            "listed specifications. The flattened_specs field contains authoritative specifications: "
            "read it carefully and cite the relevant field values before interpreting them. "
            "Those values override your prior knowledge. Never say a supplied field is absent. "
            "Do not claim tested performance or advertised benefits that are not supplied. "
            "Component names alone do not establish measured contrast, response time, "
            "frame rates or real-world gaming performance; state that suitability requires such evidence. "
            "If affordability is asked without a budget amount, report the catalog price "
            "and ask for the customer's budget instead of assuming it is affordable. "
            "A supplied product is not an empty search result. Use 1 to 3 complete sentences."
        ) if information else SYSTEM_PROMPT
        if context.get("greeting") or (context.get("general_chat") and not information):
            system_prompt = (
                "You are Poorvika Shopping Assistant. Respond naturally and briefly to the "
                "customer's greeting or general shopping question. For a greeting, welcome "
                "them and offer help finding or comparing products. No catalog search has "
                "been performed: do not claim there are no matching results. Do not invent "
                "products, prices, stock, offers or business policies."
            )
        products = context.get("products")
        if products:
            fields = ("name", "price", "in_stock", "brand", "category", "flattened_specs") if information else ("name", "price", "in_stock")
            catalog = [
                {**{key: product.get(key) for key in fields}, "currency": "INR"}
                for product in products
            ]
            prompt = f"Customer: {message}\nCatalog: {json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))}"
        else:
            prompt = f"Customer: {message}\nContext: {json.dumps(context, ensure_ascii=False, separators=(',', ':'))}"
        if information and products:
            # Highlight only existing catalog facts relevant to this question.
            # This selects evidence, never predefined answers or another LLM flow.
            import re
            terms = {term for term in re.findall(r"[a-z0-9]+", message.lower())
                     if len(term) >= 3 and term not in {"this", "that", "phone", "product", "the", "for", "how", "does", "what", "which", "can", "could", "would", "will", "with", "and", "are", "worth", "buying", "about", "have", "has", "its", "used", "use"}}
            specs = products[0].get("flattened_specs") or {}
            if terms.intersection({'processor', 'processing', 'chipset', 'cpu', 'gpu', 'gaming', 'performance'}):
                terms.update({'processor', 'chipset', 'cpu', 'gpu'})
            relevant = {key: value for key, value in specs.items()
                        if terms.intersection(re.findall(r"[a-z0-9]+", f"{key} {value}".lower()))}
            facts = "\n".join(f"{key}: {value}" for key, value in (relevant or specs).items())
            prompt = (f"Authoritative catalog specifications relevant to this question:\n{facts}\n\n"
                      f"Selected product: {json.dumps([{**catalog[0], 'flattened_specs': relevant or specs}], ensure_ascii=False)}\n\n"
                      f"Customer question: {message}\nAnswer using these supplied facts. "
                      "Do not claim a listed specification is missing.")
            if terms.intersection({'processor', 'processing', 'chipset', 'cpu'}):
                processor = {key: value for key, value in specs.items()
                             if re.search(r'\b(?:processor|chipset|cpu)\b', key, re.I)}
                if processor:
                    prompt += ('\nProcessor evidence: ' + json.dumps(processor, ensure_ascii=False) +
                               '\nCite these supplied processor values explicitly before assessing suitability; '
                               'do not replace processor evidence with GPU information or unsupported advertised benefits.')
        prompt_chars = len(system_prompt) + len(prompt)
        if timings is not None:
            timings["ollama_prompt_chars"] = prompt_chars
            timings["ollama_prompt_build_ms"] = round((time.perf_counter() - started) * 1000, 1)
        logger.info("OLLAMA prompt_chars=%d", prompt_chars)
        request_started = time.perf_counter()
        try:
            response = HTTP.post(
                self.url,
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "keep_alive": "10m",
                    "options": {"temperature": 0.0 if information else 0.1, "num_predict": 160 if information else 72, "num_ctx": 2048},
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            if timings is not None:
                timings["ollama_end"] = datetime.now(timezone.utc).isoformat()
                timings["ollama_duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
                timings["ollama_http_duration_ms"] = round((time.perf_counter() - request_started) * 1000, 1)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.info("CHAT TIMING ollama_call_ms=%.1f status=%s error=%s", (time.perf_counter() - started) * 1000, status, type(exc).__name__)
            raise
        content = (data.get("message") or {}).get("content", "").strip()
        if timings is not None:
            timings["ollama_end"] = datetime.now(timezone.utc).isoformat()
            timings["ollama_duration_ms"] = round((time.perf_counter() - started) * 1000, 1)
            timings["ollama_http_duration_ms"] = round((time.perf_counter() - request_started) * 1000, 1)
            timings["ollama_model_load_ms"] = (data.get("load_duration") or 0) / 1_000_000
            timings["ollama_prompt_eval_ms"] = (data.get("prompt_eval_duration") or 0) / 1_000_000
            timings["ollama_generation_ms"] = (data.get("eval_duration") or 0) / 1_000_000
            timings["ollama_server_total_ms"] = (data.get("total_duration") or 0) / 1_000_000
            timings["ollama_client_overhead_ms"] = round(
                max(0.0, timings["ollama_http_duration_ms"] - timings["ollama_server_total_ms"]), 1
            )
        if not content:
            logger.info("CHAT TIMING ollama_call_ms=%.1f status=%s empty=true", (time.perf_counter() - started) * 1000, response.status_code)
            raise ValueError("Ollama returned an empty response")
        logger.info("OLLAMA response received (%d characters)", len(content))
        logger.info(
            "CHAT TIMING ollama_call_ms=%.1f status=%s load_ms=%.1f prompt_eval_ms=%.1f eval_ms=%.1f eval_tokens=%s",
            (time.perf_counter() - started) * 1000,
            response.status_code,
            (data.get("load_duration") or 0) / 1_000_000,
            (data.get("prompt_eval_duration") or 0) / 1_000_000,
            (data.get("eval_duration") or 0) / 1_000_000,
            data.get("eval_count"),
        )
        return content

    def generate_suggestions(self, product: Dict[str, Any], timings: Dict[str, Any] | None = None):
        """Generate questions with the existing provider; never use static fallbacks."""
        from app.schemas.suggestions import SuggestionResponse

        prompt_started = time.perf_counter()
        listing_context = isinstance(product.get("products"), list)
        # Keep the complete request for cache identity and factual validation, but
        # avoid sending IDs, duplicate descriptions and long low-value fields to
        # the model. This matters on CPU-backed Ollama where prompt evaluation is
        # a measured part of uncached latency.
        generation_context = self._compact_suggestion_context(product, listing_context)
        prompt = (
            "Write exactly 4 distinct shopper questions, each at most 12 words. Use only the supplied catalog context; "
            "do not answer, invent facts, or imply unsupported features. End each with ?. Return only a JSON array "
            "of 4 strings."
            + (
                " This is a category listing: use its filters and supplied options collectively. Never write 'this product', "
                "'this phone', 'this mobile', or 'this item'. Avoid digits, prices, counts and storage/network numbers; "
                "cover different shopper angles."
                if listing_context else
                " This is one selected product: use its name, category, price, and supplied specifications."
            )
        )
        schema = {**SuggestionResponse.model_json_schema()["properties"]["suggestions"],
                  "minItems": 4, "maxItems": 4}
        serialized_context = json.dumps(generation_context, ensure_ascii=False, separators=(",", ":"))
        request_body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": serialized_context},
            ],
            "keep_alive": "10m",
            "options": {"temperature": 0.4, "num_predict": 96, "num_ctx": 2048},
        }
        if timings is not None:
            timings["prompt_build_ms"] = round((time.perf_counter() - prompt_started) * 1000, 3)
            timings["prompt_chars"] = len(prompt) + len(serialized_context)
            timings["context_chars"] = len(serialized_context)
            timings["context_bytes"] = len(serialized_context.encode("utf-8"))
            timings["request_context_chars"] = len(json.dumps(product, ensure_ascii=False))
        headers = {"Content-Type": "application/json"}
        if settings.OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"
        generation_started = time.perf_counter()
        validation_total_ms = 0.0
        association_total_ms = 0.0
        last_grounding_error = None
        if timings is not None:
            timings["ollama_attempts"] = []
        for attempt in range(2):  # initial generation plus one bounded factual correction
            attempt_started = time.perf_counter()
            attempt_timing = {"attempt": attempt + 1}
            if timings is not None:
                timings["ollama_started"] = datetime.now(timezone.utc).isoformat()
                timings["ollama_call_count"] = timings.get("ollama_call_count", 0) + 1
                timings["generation_attempts"] = attempt + 1
                timings["semantic_retry_count"] = attempt
            body = request_body
            if attempt:
                body = {**request_body, "messages": [
                    *request_body["messages"],
                    {"role": "assistant", "content": last_grounding_error},
                    {"role": "user", "content": "Correct the validation issue above and regenerate the full JSON array. Refer to listing categories/options collectively; check each factual value against its exact named product or variant row and do not transfer specifications between products."},
                ]}
            response = None
            try:
                response = HTTP.post(self.url, headers=headers, json=body,
                                     timeout=(3, settings.SUGGESTION_TIMEOUT_SECONDS))
                response.raise_for_status()
            except requests.RequestException as exc:
                provider_status = response.status_code if response is not None else getattr(exc.response, "status_code", None)
                error_body = " ".join((response.text if response is not None else "").split())[:1000]
                if timings is not None:
                    timings["ollama_http_status"] = provider_status
                    timings["ollama_failure_type"] = type(exc).__name__
                logger.exception("Ollama suggestion request failed request_id=%s http_status=%s response_body=%r",
                                 (timings or {}).get("request_id"), provider_status, error_body)
                attempt_timing.update(http_status=provider_status, failure_type=type(exc).__name__,
                                      ollama_wall_ms=round((time.perf_counter() - attempt_started) * 1000, 3))
                if timings is not None:
                    timings["ollama_attempts"].append(attempt_timing)
                raise
            data = response.json()
            attempt_timing.update(
                http_status=response.status_code if isinstance(response.status_code, int) else None,
                ollama_wall_ms=round((time.perf_counter() - attempt_started) * 1000, 3),
                model_load_ms=(data.get("load_duration") or 0) / 1_000_000,
                prompt_eval_ms=(data.get("prompt_eval_duration") or 0) / 1_000_000,
                generation_ms=(data.get("eval_duration") or 0) / 1_000_000,
                server_total_ms=(data.get("total_duration") or 0) / 1_000_000,
            )
            content = (data.get("message") or {}).get("content", "")
            parse_started = time.perf_counter()
            try:
                parsed = json.loads(content)
            except (TypeError, json.JSONDecodeError) as exc:
                attempt_timing["parse_ms"] = round((time.perf_counter() - parse_started) * 1000, 3)
                if timings is not None:
                    timings["ollama_attempts"].append(attempt_timing)
                if timings is not None:
                    timings["output_parse_ms"] = round((time.perf_counter() - parse_started) * 1000, 3)
                raise ValueError("Generated suggestions were not a JSON array") from exc
            if timings is not None:
                timings["output_parse_ms"] = round((time.perf_counter() - parse_started) * 1000, 3)
            validation_started = time.perf_counter()
            association_started = time.perf_counter()
            try:
                if not isinstance(parsed, list):
                    raise ValueError("Generated suggestions must be a JSON array")
                result = SuggestionResponse(suggestions=parsed)
                if len(result.suggestions) != 4:
                    raise ValueError("Generated suggestions must contain exactly four questions")
                if listing_context and any(re.search(r"\bthis\s+(?:product|phone|mobile|item)\b", question, re.I)
                                           for question in result.suggestions):
                    raise SuggestionGroundingError("Listing suggestions cannot refer to one selected product")
                # Retain the existing cross-context number guard, then verify values
                # are present on the exact model rows named in listing questions.
                def numbers(text):
                    return {Decimal(value.replace(",", ""))
                            for value in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", text)}
                supplied_numbers = numbers(json.dumps(product, ensure_ascii=False))
                for question in result.suggestions:
                    if not numbers(question).issubset(supplied_numbers):
                        raise SuggestionGroundingError("Generated suggestion contains an unsupported numeric fact")
                if listing_context:
                    try:
                        _validate_listing_fact_associations(result.suggestions, product)
                    finally:
                        association_total_ms += (time.perf_counter() - association_started) * 1000
                validate_suggestion_claims(result.suggestions, product)
                if timings is not None:
                    timings["validated"] = datetime.now(timezone.utc).isoformat()
                    timings["ollama_ms"] = round((time.perf_counter() - generation_started) * 1000, 3)
                    timings["ollama_server_generation_ms"] = (data.get("eval_duration") or 0) / 1_000_000
                    timings["ollama_load_ms"] = (data.get("load_duration") or 0) / 1_000_000
                    timings["ollama_prompt_eval_ms"] = (data.get("prompt_eval_duration") or 0) / 1_000_000
                    timings["ollama_server_total_ms"] = (data.get("total_duration") or 0) / 1_000_000
                    timings["ollama_prompt_eval_tokens"] = data.get("prompt_eval_count")
                    timings["ollama_generation_tokens"] = data.get("eval_count")
                    timings["association_validation_ms"] = round(association_total_ms, 3)
                    timings["validation_ms"] = round(validation_total_ms + (time.perf_counter() - validation_started) * 1000, 3)
                return result
            except SuggestionGroundingError as exc:
                last_grounding_error = str(exc)
                logger.warning("Suggestion semantic grounding failed request_id=%s attempt=%d reason=%s",
                               (timings or {}).get("request_id"), attempt + 1, exc)
                if attempt == 1:
                    raise
            finally:
                elapsed_ms = (time.perf_counter() - validation_started) * 1000
                validation_total_ms += elapsed_ms
                attempt_timing["parse_ms"] = timings.get("output_parse_ms", 0) if timings is not None else 0
                attempt_timing["validation_ms"] = round(elapsed_ms, 3)
                attempt_timing["ollama_wall_ms"] = round((time.perf_counter() - attempt_started) * 1000, 3)
                if timings is not None:
                    timings["ollama_attempts"].append(attempt_timing)
                    timings["association_validation_ms"] = round(association_total_ms, 3)
                    timings["validation_ms"] = round(validation_total_ms, 3)
        raise last_grounding_error or ValueError("Could not generate grounded suggestions")

    @staticmethod
    def _compact_suggestion_context(product: Dict[str, Any], listing_context: bool):
        """Build a small, catalog-grounded context for question generation."""
        def specs(value, limit, value_limit=140):
            if isinstance(value, list):
                entries = [(str(item.get("name", "")), item.get("value")) for item in value if isinstance(item, dict)]
            elif isinstance(value, dict):
                entries = list(value.items())
            else:
                return {}
            priorities = (
                ("processor", 10), ("chipset", 10), ("camera", 10), ("battery", 9),
                ("display", 9), ("screen", 9), ("storage", 8), ("memory", 8), ("ram", 8),
                ("network", 8), ("connectivity", 8), ("gps", 7), ("operating system", 7),
                ("water resistance", 7), ("refresh rate", 7), ("audio", 7), ("bluetooth", 6),
                ("warranty", 5), ("weight", 3), ("dimension", 2),
            )
            indexed = list(enumerate(entries))
            indexed.sort(key=lambda pair: (-max((score for term, score in priorities if term in str(pair[1][0]).lower()), default=1), pair[0]))
            output = {}
            for _, (key, raw) in indexed[:limit]:
                if raw is None:
                    continue
                text = " ".join(str(raw).split())
                output[str(key)[:80]] = text[:value_limit]
            return output

        if listing_context:
            results = []
            for row in product.get("products", [])[:5]:
                if not isinstance(row, dict):
                    continue
                compact = {key: row[key] for key in ("name", "brand", "category", "price") if row.get(key) is not None}
                compact_specs = specs(row.get("specifications"), 2, 90)
                if compact_specs:
                    compact["specifications"] = compact_specs
                results.append(compact)
            context = {key: product[key] for key in ("name", "category", "query", "filters") if product.get(key) is not None}
            context["products"] = results
            return context

        context = {key: product[key] for key in ("name", "brand", "category", "price") if product.get(key) is not None}
        description = product.get("description")
        if description and " ".join(str(description).split()).casefold() != " ".join(str(product.get("name", "")).split()).casefold():
            context["description"] = " ".join(str(description).split())[:180]
        compact_specs = specs(product.get("specifications"), 8)
        if compact_specs:
            context["specifications"] = compact_specs
        return context

    @staticmethod
    def product_context(products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Keep only catalog-backed fields in the prompt context."""
        return {
            "products": [
                {
                    key: product.get(key)
                    for key in (
                        "id", "name", "brand", "model", "category", "price", "mrp",
                        "discount_percent", "in_stock", "stock", "rating", "rating_count",
                        # Names, price, stock and rating are enough for concise
                        # product recommendations; large raw descriptions/specs
                        # needlessly inflate local inference prompts.
                    )
                }
                for product in products
            ]
        }
