/* app.core.js 逻辑测试：node scripts/test_web_core.js */
"use strict";
const assert = require("assert");
const PPLORA = require("../web/app.core.js");
const fs = require("fs");
const path = require("path");

// 加载生成题库（bank.js 在浏览器全局挂 PERSONA_BANK）
const sandbox = {};
new Function("globalThis", fs.readFileSync(path.join(__dirname, "../web/data/bank.js"), "utf8"))(sandbox);
const bank = sandbox.PERSONA_BANK;

assert.ok(bank && bank.scenes.length === 7, "7 场景");
assert.strictEqual(bank.scenes.reduce((n, s) => n + s.questions.length, 0), 92, "92 题");
const wq = bank.scenes.find(s => s.id === "work_communication");
assert.ok(wq.questions[0].qid === "work_communication#0", "qid 格式");

// ---- 隐私打码 ----
let m = PPLORA.maskPrivacy("打我电话13912345678聊");
assert.ok(m.text.includes("【手机号】") && !m.text.includes("13912345678"), "手机号打码");
m = PPLORA.maskPrivacy("身份证110101199003077512你看");
assert.ok(m.text.includes("【身份证】"), "身份证打码");
m = PPLORA.maskPrivacy("发我邮箱 foo.bar@x.co 和链接 https://a.b/c?d=1 哈");
assert.ok(m.text.includes("【邮箱】") && m.text.includes("【链接】"), "邮箱/链接打码");
m = PPLORA.maskPrivacy("哎这需求有点赶啊……明天给你答复行不");
assert.strictEqual(m.hits.length, 0, "正常口语零命中");
assert.strictEqual(m.text, "哎这需求有点赶啊……明天给你答复行不", "原文一字不改");
// 普通数字串（如价格）不应误伤
m = PPLORA.maskPrivacy("这个要 2000 块，日期 2024-05-01");
assert.strictEqual(m.hits.length, 0, "普通数字不误伤");

// ---- 样本构建 ----
const state = {
  name: "老王", mode: "single", scenes: ["work_communication", "daily_social"],
  answers: {},
};
wq.questions.slice(0, 3).forEach(q => { state.answers[q.qid] = "我觉得吧，先搞定主要的再说！"; });
const rows = PPLORA.buildTrainRows(bank, state);
assert.strictEqual(rows.length, 3, "已答 3 行");
assert.strictEqual(rows[0].messages.length, 3, "system+user+assistant");
assert.strictEqual(rows[0].messages[0].role, "system");
assert.ok(rows[0].messages[0].content.includes("老王"), "系统提示词替换昵称");
assert.strictEqual(rows[0].messages[2].role, "assistant", "结尾 assistant");
assert.ok(rows[0].messages[1].content.startsWith("（"), "context 前缀");

// ---- 就绪度 / 多场景校验 ----
let ready = PPLORA.readiness(bank, state);
assert.strictEqual(ready.total, 3);
assert.ok(!ready.okBasic && !ready.okOptimal, "3 条未达标");
state.mode = "multi";
ready = PPLORA.readiness(bank, state);
assert.ok(ready.multiBlocked && ready.weakScenes.length === 2, "多场景弱场景拦截");
state.mode = "single";

// ---- 切分与 jsonl ----
for (let i = 3; i < wq.questions.length + 10; i++) { /* 补到 30 条 */ }
wq.questions.forEach(q => { state.answers[q.qid] = "嗯嗯，这个我熟，听我说——" + q.idx; });
bank.scenes.find(s => s.id === "daily_social").questions.forEach(q => {
  state.answers[q.qid] = "哈哈哈真的假的！";
});
let rows2 = PPLORA.buildTrainRows(bank, state);
assert.strictEqual(rows2.length, 29, "15+14=29");
const split = PPLORA.splitTrainVal(rows2, 42, 0.05);
assert.strictEqual(split.train.length + split.validation.length, 29);
assert.strictEqual(split.validation.length, Math.max(1, Math.floor(29 * 0.05)), "≥20 条才切 5%");
const text = PPLORA.jsonlText(split.train);
const lines = text.trim().split("\n").map(l => JSON.parse(l));
assert.ok(lines.every(r => r.messages[r.messages.length - 1].role === "assistant"), "每行以 assistant 结尾");

// ---- CSV 模板 / 解析 / 回传 ----
const csv = PPLORA.blankCsvText(bank);
assert.ok(csv.startsWith('"qid","scene_id","scene_name"'), "模板表头");
const parsed = PPLORA.parseCsv("\ufeff" + csv);
assert.strictEqual(parsed.length, 92, "模板行数");
const escVal = '有逗号，还有"引号"';
const quotedCsv = '"qid","answer"\n' + '"a#1"' + ',' + '"' + escVal.replace(/"/g, '""') + '"' + '\n';
const quoted = PPLORA.parseCsv(quotedCsv);
assert.strictEqual(quoted[0].answer, escVal, "引号转义解析");
const crlf = PPLORA.parseCsv("qid,answer\r\na#2,回车换行\r\n");
assert.strictEqual(crlf[0].answer, "回车换行", "CRLF 解析");

const filled = PPLORA.blankCsvText(bank)
  .split("\r\n").map((l, i) => (i === 1 ? l.replace(/,""$/, ',"CSV 填写的答案"') : l))
  .join("\r\n");
const res = PPLORA.csvToAnswers(bank, PPLORA.parseCsv(filled), {});
assert.strictEqual(res.matched, 1, "CSV 按 qid 命中");

// ---- exportPack ----
const pack = PPLORA.exportPack(bank, state, "2026-10-09T00:00:00Z");
assert.strictEqual(pack.answersDoc.app, "personal-lora-llm-web");
assert.strictEqual(pack.answersDoc.answers.length, 29, "answers.json 收录已答");
assert.ok(pack.answersDoc.answers.every(a => a.qid && a.answer), "answer 非空");
assert.strictEqual(pack.card.totalUsable, 29);
const back = PPLORA.mergeAnswersDoc(pack.answersDoc, { name: "", mode: "single", scenes: [], answers: {} });
assert.ok(back.ok && back.imported === 29, "answers.json 回传合并");
assert.ok(!PPLORA.mergeAnswersDoc({ foo: 1 }, state).ok, "非法文档拒绝");

console.log("✅ web core tests ALL PASS (bank 7 场景/92 题, 样本构建/打码/切分/CSV/导出包)");
