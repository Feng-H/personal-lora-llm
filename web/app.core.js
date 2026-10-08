/* Personal Persona LoRA · 网页问卷核心逻辑（纯函数，无 DOM；浏览器与 node 通用）
 * 规则与 persona_lora/cleaning.py、persona_lora/export.py 严格对齐：
 * - 隐私明文打码（手机号/身份证/银行卡/邮箱/链接），不改写其余任何内容
 * - train.jsonl = Qwen messages 格式，结尾必须是 assistant
 * - ≥70 条基础版 / ≥120 条最优；多场景模式每场景 ≥ minSamplesMulti 强制校验
 */
(function (global) {
  "use strict";
  var PPLORA = {};

  /* ---------- 随机与洗牌（可复现，与导出口径一致即可） ---------- */
  PPLORA.mulberry32 = function (seed) {
    var a = (seed || 42) >>> 0;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  PPLORA.shuffled = function (arr, seed) {
    var a = arr.slice();
    var rng = PPLORA.mulberry32(seed === undefined ? 42 : seed);
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  };

  /* ---------- 隐私打码（捕获组代替 lookbehind，兼容老 Safari） ---------- */
  var PRIVACY_RULES = [
    ["手机号", /(^|[^\d])(1[3-9]\d{9})(?!\d)/g],
    ["身份证", /(^|[^\d])(\d{17}[\dXx])(?!\d)/g],
    ["银行卡", /(^|[^\d])(\d{16,19})(?!\d)/g],
    ["邮箱", /([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g],
    ["链接", /(https?:\/\/\S+|www\.\S+)/g],
  ];
  PPLORA.maskPrivacy = function (text) {
    var out = String(text);
    var hits = [];
    PRIVACY_RULES.forEach(function (rule) {
      var label = rule[0], re = rule[1];
      out = out.replace(re, function (m, p1, p2) {
        hits.push(label);
        return p2 !== undefined ? p1 + "【" + label + "】" : "【" + label + "】";
      });
    });
    return { text: out, hits: hits };
  };

  /* ---------- 样本构建 ---------- */
  PPLORA.buildSystemPrompt = function (scene, userName) {
    return String(scene.systemPrompt || "")
      .replace(/\{user_name\}/g, userName || "你").trim();
  };
  PPLORA.buildUserContent = function (q) {
    return q.context ? "（" + q.context + "）" + q.question : q.question;
  };

  PPLORA.sceneById = function (bank) {
    var m = {};
    (bank.scenes || []).forEach(function (s) { m[s.id] = s; });
    return m;
  };

  PPLORA.sceneCounts = function (bank, state) {
    var byId = PPLORA.sceneById(bank);
    var counts = {};
    (state.scenes || []).forEach(function (sid) {
      var scene = byId[sid];
      if (!scene) { counts[sid] = 0; return; }
      var n = 0;
      scene.questions.forEach(function (q) {
        if ((state.answers[q.qid] || "").trim()) n++;
      });
      counts[sid] = n;
    });
    return counts;
  };

  /* 训练样本行（仅含已作答题目；assistant 为打码后的原文） */
  PPLORA.buildTrainRows = function (bank, state) {
    var byId = PPLORA.sceneById(bank);
    var rows = [];
    (state.scenes || []).forEach(function (sid) {
      var scene = byId[sid];
      if (!scene) return;
      scene.questions.forEach(function (q) {
        var raw = (state.answers[q.qid] || "").trim();
        if (!raw) return;
        var masked = PPLORA.maskPrivacy(raw);
        rows.push({
          scene: sid, qid: q.qid, maskHits: masked.hits.length,
          messages: [
            { role: "system", content: PPLORA.buildSystemPrompt(scene, state.name) },
            { role: "user", content: PPLORA.buildUserContent(q) },
            { role: "assistant", content: masked.text },
          ],
        });
      });
    });
    return rows;
  };

  /* train/validation 切分（与 export.py 相同规则：≥20 条才切 5%） */
  PPLORA.splitTrainVal = function (rows, seed, ratio) {
    var r = ratio === undefined ? 0.05 : ratio;
    var shuffled = PPLORA.shuffled(rows, seed === undefined ? 42 : seed);
    var nVal = shuffled.length >= 20 ? Math.max(1, Math.floor(shuffled.length * r)) : 0;
    return { validation: shuffled.slice(0, nVal), train: shuffled.slice(nVal) };
  };

  PPLORA.jsonlText = function (rows) {
    return rows.map(function (r) { return JSON.stringify({ messages: r.messages }); }).join("\n") + "\n";
  };

  /* ---------- 就绪度（70/120 阈值 + 多场景强制校验，与工作台一致） ---------- */
  PPLORA.readiness = function (bank, state) {
    var byId = PPLORA.sceneById(bank);
    var counts = PPLORA.sceneCounts(bank, state);
    var multi = state.mode === "multi";
    var perScene = (state.scenes || []).map(function (sid) {
      var scene = byId[sid];
      var need = scene ? (multi ? scene.minSamplesMulti : scene.minSamplesSingle) : 0;
      var have = counts[sid] || 0;
      return {
        id: sid, name: scene ? scene.name : sid, icon: scene ? scene.icon : "🏷️",
        have: have, need: need, gap: Math.max(0, need - have),
      };
    });
    var total = Object.keys(counts).reduce(function (n, sid) { return n + counts[sid]; }, 0);
    var weak = perScene.filter(function (p) { return p.gap > 0; });
    return {
      total: total, basic: 70, optimal: 120,
      okBasic: total >= 70, okOptimal: total >= 120,
      perScene: perScene,
      multiBlocked: multi && weak.length > 0,
      weakScenes: weak,
    };
  };

  /* ---------- 导出包 ---------- */
  PPLORA.exportPack = function (bank, state, nowIso) {
    var rows = PPLORA.buildTrainRows(bank, state);
    var ready = PPLORA.readiness(bank, state);
    var split = PPLORA.splitTrainVal(rows, 42, 0.05);
    var byId = PPLORA.sceneById(bank);
    var stamp = nowIso || new Date().toISOString();

    /* answers.json：无损中间格式（保存原文，供本地工作台再清洗） */
    var answers = [];
    (state.scenes || []).forEach(function (sid) {
      var scene = byId[sid];
      if (!scene) return;
      scene.questions.forEach(function (q) {
        var raw = (state.answers[q.qid] || "").trim();
        if (!raw) return;
        answers.push({
          qid: q.qid, scene: sid, context: q.context,
          question: q.question, answer: raw,
        });
      });
    });
    var answersDoc = {
      app: "personal-lora-llm-web", version: 1, exportedAt: stamp,
      user: { name: state.name || "", mode: state.mode || "single", scenes: (state.scenes || []).slice() },
      answers: answers,
    };

    var card = {
      source: "web", generatedAt: stamp,
      trainSamples: split.train.length,
      validationSamples: split.validation.length,
      totalUsable: rows.length,
      scenes: (state.scenes || []).reduce(function (o, sid) {
        o[sid] = byId[sid] ? byId[sid].name : sid; return o;
      }, {}),
      mode: state.mode || "single",
      privacyMasked: rows.reduce(function (n, r) { return n + r.maskHits; }, 0),
    };
    return {
      ready: ready, answersDoc: answersDoc, card: card,
      trainText: PPLORA.jsonlText(split.train),
      valText: split.validation.length ? PPLORA.jsonlText(split.validation) : "",
    };
  };

  /* ---------- CSV：模板下载 / 已填回传 ---------- */
  var csvEsc = function (v) {
    return '"' + String(v === undefined || v === null ? "" : v).replace(/"/g, '""') + '"';
  };
  PPLORA.blankCsvText = function (bank) {
    var lines = [["qid", "scene_id", "scene_name", "context", "question", "answer"].map(csvEsc).join(",")];
    (bank.scenes || []).forEach(function (s) {
      s.questions.forEach(function (q) {
        lines.push([q.qid, s.id, s.name, q.context, q.question, ""].map(csvEsc).join(","));
      });
    });
    return lines.join("\r\n") + "\r\n";
  };

  PPLORA.parseCsv = function (text) {
    var t = String(text).replace(/^\ufeff/, "");
    var rows = [], row = [], field = "", inQ = false;
    for (var i = 0; i < t.length; i++) {
      var c = t[i];
      if (inQ) {
        if (c === '"') {
          if (t[i + 1] === '"') { field += '"'; i++; } else { inQ = false; }
        } else { field += c; }
      } else if (c === '"') { inQ = true; }
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
      else if (c === "\r") { /* \r\n 由 \n 收尾 */ }
      else { field += c; }
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    if (!rows.length) return [];
    var head = rows[0].map(function (h) { return h.trim(); });
    return rows.slice(1)
      .filter(function (r) { return r.some(function (x) { return x !== ""; }); })
      .map(function (r) {
        var o = {};
        head.forEach(function (h, i) { o[h] = (r[i] === undefined ? "" : r[i]).trim(); });
        return o;
      });
  };

  PPLORA.csvToAnswers = function (bank, rows, answers) {
    var byQid = {}, bySq = {};
    (bank.scenes || []).forEach(function (s) {
      s.questions.forEach(function (q) {
        byQid[q.qid] = q;
        bySq[s.id + "\u0000" + q.question] = q;
      });
    });
    var merged = Object.assign({}, answers);
    var matched = 0, unmatched = 0;
    rows.forEach(function (r) {
      var answer = (r.answer || "").trim();
      if (!answer) return;
      var q = r.qid ? byQid[r.qid] : null;
      if (!q && r.scene_id) q = bySq[r.scene_id + "\u0000" + (r.question || "").trim()];
      if (q) { merged[q.qid] = answer; matched++; } else { unmatched++; }
    });
    return { merged: merged, matched: matched, unmatched: unmatched };
  };

  /* answers.json 回传合并（跨设备迁移） */
  PPLORA.mergeAnswersDoc = function (doc, state) {
    if (!doc || doc.app !== "personal-lora-llm-web" || !Array.isArray(doc.answers)) {
      return { ok: false, error: "不是有效的 answers.json（缺 app 标识或 answers 数组）" };
    }
    var answers = Object.assign({}, state.answers);
    var n = 0;
    doc.answers.forEach(function (a) {
      if (a && a.qid && (a.answer || "").trim()) { answers[a.qid] = String(a.answer).trim(); n++; }
    });
    var merged = {
      name: state.name || (doc.user && doc.user.name) || "",
      mode: (doc.user && doc.user.mode) || state.mode,
      scenes: state.scenes.length ? state.scenes : ((doc.user && doc.user.scenes) || []),
      answers: answers,
    };
    return { ok: true, state: merged, imported: n };
  };

  global.PPLORA = PPLORA;
  if (typeof module !== "undefined" && module.exports) { module.exports = PPLORA; }
})(typeof window !== "undefined" ? window : globalThis);
