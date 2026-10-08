/* 个人人格问卷 · DOM 交互（localStorage 自动保存 / 导出 / 导入）
 * 安全约定：所有动态内容一律 createElement + textContent 构建，不用 innerHTML
 * （题库内容来自用户可自定义的 CSV，按不可信输入处理）
 */
(function () {
  "use strict";
  var BANK = window.PERSONA_BANK;
  var P = window.PPLORA;
  var LS_KEY = "pplora.web.v1";
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null && text !== "") {
      node.textContent = String(text);
    }
    return node;
  }

  /* ---------- 状态 ---------- */
  var state = loadState();

  function loadState() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (raw) {
        var s = JSON.parse(raw);
        if (s && typeof s === "object" && s.answers) {
          s.name = s.name || ""; s.mode = s.mode || "single";
          s.scenes = Array.isArray(s.scenes) ? s.scenes : [];
          return s;
        }
      }
    } catch { /* 隐私模式/损坏数据 → 全新开始 */ }
    return {
      name: "", mode: "single", scenes: ["work_communication"],
      answers: {}, activeScene: "work_communication",
    };
  }
  function saveState() {
    state.updatedAt = new Date().toISOString();
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); setSaveIndicator(true); }
    catch { $("saveState").textContent = "⚠️ 无法本地保存，请及时导出"; }
  }
  var saveTimer = null;
  function saveSoon() {
    setSaveIndicator(false);
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(saveState, 400);
  }
  function setSaveIndicator(clean) {
    var elx = $("saveState");
    elx.classList.toggle("dirty", !clean);
    elx.textContent = clean
      ? "已自动保存 · " + new Date().toTimeString().slice(0, 5)
      : "保存中…";
  }

  function toast(msg) {
    var t = $("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._t);
    t._t = setTimeout(function () { t.classList.remove("show"); }, 2600);
  }

  function sceneById(id) {
    for (var i = 0; i < BANK.scenes.length; i++) if (BANK.scenes[i].id === id) return BANK.scenes[i];
    return null;
  }

  /* ---------- 渲染 ---------- */
  function renderSettings() {
    $("userName").value = state.name;
    Array.prototype.forEach.call($("modeSeg").children, function (btn) {
      btn.classList.toggle("on", btn.dataset.mode === state.mode);
    });
    var chips = $("sceneChips");
    chips.textContent = "";
    BANK.scenes.forEach(function (s) {
      var on = state.scenes.indexOf(s.id) !== -1;
      var chip = el("button", "chip" + (on ? " on" : ""), s.icon + " " + s.name);
      chip.type = "button";
      chip.appendChild(el("span", "n", s.questions.length + " 题"));
      chip.addEventListener("click", function () {
        var i = state.scenes.indexOf(s.id);
        if (i === -1) {
          state.scenes.push(s.id);
          if (!sceneById(state.activeScene)) state.activeScene = s.id;
        } else if (state.scenes.length > 1) {
          state.scenes.splice(i, 1);
          if (state.activeScene === s.id) state.activeScene = state.scenes[0];
        } else {
          toast("至少保留 1 个场景");
          return;
        }
        saveSoon(); renderAll();
      });
      chips.appendChild(chip);
    });
    var n = state.scenes.length;
    $("sceneHint").textContent = state.mode === "multi"
      ? "多场景全能：已选 " + n + " 个场景。导出时每个场景都必须达到最低样本数（默认 45 条/场景），防止风格混杂。"
      : "单场景专精：只训练单一人格，风格纯净、快速成型。目标 70 条起。";
  }

  function answeredIn(scene) {
    var n = 0;
    scene.questions.forEach(function (q) { if ((state.answers[q.qid] || "").trim()) n++; });
    return n;
  }

  function renderTabs() {
    var tabs = $("sceneTabs");
    tabs.textContent = "";
    state.scenes.forEach(function (id) {
      var s = sceneById(id);
      if (!s) return;
      var tab = el("button", "tab" + (state.activeScene === id ? " on" : ""));
      tab.type = "button";
      tab.appendChild(document.createTextNode(s.icon + " " + s.name));
      tab.appendChild(el("span", "done", answeredIn(s) + "/" + s.questions.length));
      tab.addEventListener("click", function () {
        state.activeScene = id;
        saveSoon(); renderFill();
      });
      tabs.appendChild(tab);
    });
  }

  function statBlock(cls, big, label) {
    var d = el("div", "stat" + (cls ? " " + cls : ""));
    d.appendChild(el("b", null, big));
    d.appendChild(el("span", null, label));
    return d;
  }

  function renderFill() {
    renderTabs();
    var list = $("questionList");
    list.textContent = "";
    var scene = sceneById(state.activeScene);
    if (!scene) {
      list.appendChild(el("p", "hint", "先在「基本设置」里勾选场景，题目会出现在这里。"));
      return;
    }
    scene.questions.forEach(function (q, i) {
      var d = document.createElement("details");
      d.className = "q";
      d.dataset.qid = q.qid;

      var summary = document.createElement("summary");
      summary.appendChild(el("span", "q-no", scene.icon + " Q" + (i + 1)));
      summary.appendChild(el("span", "q-title", q.question));
      var st = el("span", "q-state", "待答");
      summary.appendChild(st);
      d.appendChild(summary);

      var body = el("div", "q-body");
      if (q.context) body.appendChild(el("p", "q-context", "📍 情境：" + q.context));
      var ta = document.createElement("textarea");
      ta.placeholder = "用你平时的口吻，怎么聊天就怎么打字……";
      body.appendChild(ta);
      var note = el("p", "q-note");
      body.appendChild(note);
      d.appendChild(body);
      list.appendChild(d);

      ta.value = state.answers[q.qid] || "";
      function refresh() {
        var val = ta.value;
        state.answers[q.qid] = val;
        if (val.trim()) {
          st.textContent = "✓ 已答";
          st.classList.add("answered");
        } else {
          st.textContent = "待答";
          st.classList.remove("answered");
        }
        var masked = P.maskPrivacy(val);
        if (val.trim() && masked.hits.length) {
          note.textContent = "🔒 已自动打码：" + masked.hits.join("、") + "（导出时生效）";
          note.classList.add("masked");
        } else if (val.trim()) {
          note.textContent = "✓ 原文保留：语气词、标点、重复强调都会完整进入训练集";
          note.classList.remove("masked");
        } else {
          note.textContent = "";
        }
      }
      ta.addEventListener("input", function () { refresh(); saveSoon(); updateStatsSoon(); });
      if (ta.value) refresh();
    });
  }

  function renderReadiness() {
    var ready = P.readiness(BANK, state);
    var box = $("readiness");
    box.textContent = "";

    var grid = el("div", "readiness-grid");
    grid.appendChild(statBlock(ready.okOptimal ? "ok" : "", ready.total, "有效样本"));
    grid.appendChild(statBlock(ready.okBasic ? "ok" : "warn", ready.okBasic ? "✓" : ready.basic, "基础线 70 条"));
    grid.appendChild(statBlock(ready.okOptimal ? "ok" : "", ready.okOptimal ? "✓" : ready.optimal, "最优 120 条"));
    box.appendChild(grid);

    var bars = el("div", "scene-bars");
    ready.perScene.forEach(function (p) {
      var pct = p.need ? Math.min(100, Math.round(p.have / p.need * 100)) : 100;
      var row = el("div", "scene-bar", p.icon + " " + p.name + "：" + p.have + " / " + p.need);
      var track = el("div", "track");
      var fill = el("div", "fill");
      fill.style.width = pct + "%";
      track.appendChild(fill);
      row.appendChild(track);
      bars.appendChild(row);
    });
    box.appendChild(bars);

    var note;
    if (ready.multiBlocked) {
      note = el("p", "block-note", "⛔ 多场景模式强制校验："
        + ready.weakScenes.map(function (w) { return w.name + " 缺 " + w.gap + " 条"; }).join("、")
        + "。补齐后再导出可防风格混杂（也可确认后试导出）。");
    } else if (ready.okOptimal) {
      note = el("p", "ok-note", "🎉 已达最优体量（≥120 条）：直接下载 train.jsonl 上传 Kaggle 即可训练完整版人格。");
    } else if (ready.okBasic) {
      note = el("p", "ok-note", "✅ 已达基础线（≥70 条）：可以导出训练。继续积累到 120 条效果更完整。");
    } else {
      note = el("p", "block-note", "⏳ 还差 " + (ready.basic - ready.total) + " 条达到基础线（70 条）。也可以先试导出跑通 Kaggle 流程。");
    }
    box.appendChild(note);
    return ready;
  }

  var statsTimer = null;
  function updateStatsSoon() {
    if (statsTimer) clearTimeout(statsTimer);
    statsTimer = setTimeout(function () { renderReadiness(); renderTabs(); updateProgress(); }, 300);
  }
  function updateProgress() {
    var counts = P.sceneCounts(BANK, state);
    var total = 0;
    Object.keys(counts).forEach(function (k) { total += counts[k]; });
    $("progressFill").style.width = Math.min(100, total / 120 * 100) + "%";
  }

  function renderAll() { renderSettings(); renderFill(); renderReadiness(); updateProgress(); }

  /* ---------- 下载 ---------- */
  function download(name, text, mime) {
    var blob = new Blob([text], { type: (mime || "text/plain") + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  /* ---------- 事件 ---------- */
  $("userName").addEventListener("input", function () {
    state.name = this.value.trim();
    saveSoon();
  });
  Array.prototype.forEach.call($("modeSeg").children, function (btn) {
    btn.addEventListener("click", function () {
      state.mode = btn.dataset.mode;
      saveSoon(); renderAll();
    });
  });

  $("btnTrain").addEventListener("click", function () {
    var pack = P.exportPack(BANK, state);
    var ready = pack.ready;
    var blocked = (!ready.okBasic || ready.multiBlocked);
    if (blocked && !window.confirm(
      (ready.multiBlocked ? "多场景校验未通过（存在薄弱场景，可能风格混杂）。\n" : "样本未达 70 条基础线。\n")
      + "仍要试导出（仅供跑通 Kaggle 流程）？"
    )) return;
    download("train.jsonl", pack.trainText, "application/jsonl");
    if (pack.valText) download("validation.jsonl", pack.valText, "application/jsonl");
    download("dataset_card.json", JSON.stringify(pack.card, null, 2), "application/json");
    toast("已下载 train/validation + 数据集卡片（打码 " + pack.card.privacyMasked + " 处）");
  });

  $("btnAnswers").addEventListener("click", function () {
    var pack = P.exportPack(BANK, state);
    download("answers.json", JSON.stringify(pack.answersDoc, null, 2), "application/json");
    toast("answers.json 已下载：可在本地工作台继续积累对话/IM 样本");
  });

  $("btnCsvTpl").addEventListener("click", function () {
    download("persona-questionnaire-template.csv", "\ufeff" + P.blankCsvText(BANK), "text/csv");
    toast("空白 CSV 模板已下载（Excel 直接可开）");
  });

  $("fileAnswers").addEventListener("change", function () {
    var f = this.files && this.files[0];
    if (!f) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var doc = JSON.parse(reader.result);
        var res = P.mergeAnswersDoc(doc, state);
        if (!res.ok) { toast("❌ " + res.error); return; }
        state = res.state;
        saveState(); renderAll();
        toast("已导入 " + res.imported + " 条答卷 ✅");
      } catch { toast("❌ JSON 解析失败"); }
    };
    reader.readAsText(f, "utf-8");
    this.value = "";
  });

  $("fileCsv").addEventListener("change", function () {
    var f = this.files && this.files[0];
    if (!f) return;
    var reader = new FileReader();
    reader.onload = function () {
      var rows = P.parseCsv(reader.result);
      if (!rows.length) { toast("❌ CSV 为空或格式不对"); return; }
      var res = P.csvToAnswers(BANK, rows, state.answers);
      state.answers = res.merged;
      saveState(); renderAll();
      toast("CSV 导入：命中 " + res.matched + " 条" + (res.unmatched ? "，未匹配 " + res.unmatched + " 条" : ""));
    };
    reader.readAsText(f, "utf-8");
    this.value = "";
  });

  $("btnReset").addEventListener("click", function () {
    if (!window.confirm("确定清空本浏览器里保存的所有填写记录？建议先导出 answers.json 备份。")) return;
    try { localStorage.removeItem(LS_KEY); } catch { /* 忽略 */ }
    state = loadState();
    renderAll();
    toast("已清空，从头开始");
  });

  /* ---------- 启动 ---------- */
  if (!BANK || !BANK.scenes || !BANK.scenes.length) {
    document.body.textContent = "题库数据缺失：请先运行 python scripts/build_web_bank.py";
    return;
  }
  if (!sceneById(state.activeScene)) state.activeScene = state.scenes[0] || BANK.scenes[0].id;
  if (!state.scenes.length) state.scenes = [state.activeScene];
  renderAll();
  setSaveIndicator(true);
})();
