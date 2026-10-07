/** Opt-in ShopAI entry point. Legacy server/defaults remain unchanged. */
import {start} from '../evaluation/laya_specialist_onnx_isolated/integration/service.mjs';
process.env.PORT ||= '5056';
await start();
