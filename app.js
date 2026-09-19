if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'pdf.worker.min.js';
}

// Application State
let currentTransactions = [];
let currentValidation = null;
let currentFilter = 'all'; // 'all' or 'needs_review'

// Local Storage Keys
const STORAGE_KEY_ANTHROPIC = 'statementflow_anthropic_key';
const STORAGE_KEY_MODEL = 'statementflow_anthropic_model';

// DOM Elements
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const loadingText = document.getElementById('loadingText');
const errorBanner = document.getElementById('errorBanner');
const errorTitle = document.getElementById('errorTitle');
const errorMessage = document.getElementById('errorMessage');
const reviewSection = document.getElementById('reviewSection');
const validationBanner = document.getElementById('validationBanner');
const validationIcon = document.getElementById('validationIcon');
const validationTitle = document.getElementById('validationTitle');
const validationList = document.getElementById('validationList');
const extractionEngineTag = document.getElementById('extractionEngineTag');
const tableBody = document.getElementById('tableBody');
const searchInput = document.getElementById('searchInput');
const exportCsvBtn = document.getElementById('exportCsvBtn');
const exportAuditCsvBtn = document.getElementById('exportAuditCsvBtn');
const copyBtn = document.getElementById('copyBtn');
const addRowBtn = document.getElementById('addRowBtn');
const clearBtn = document.getElementById('clearBtn');
const statCount = document.getElementById('statCount');
const statConfidence = document.getElementById('statConfidence');
const statConfidenceSub = document.getElementById('statConfidenceSub');
const statNeedsReview = document.getElementById('statNeedsReview');
const statReviewBox = document.getElementById('statReviewBox');
const statDebits = document.getElementById('statDebits');
const statCredits = document.getElementById('statCredits');
const statExpectedDebits = document.getElementById('statExpectedDebits');
const statExpectedCredits = document.getElementById('statExpectedCredits');

// Filter Tabs & Review Banner
const tabAll = document.getElementById('tabAll');
const tabNeedsReview = document.getElementById('tabNeedsReview');
const countAll = document.getElementById('countAll');
const countReview = document.getElementById('countReview');
const reviewNoticeBanner = document.getElementById('reviewNoticeBanner');
const reviewNoticeCount = document.getElementById('reviewNoticeCount');
const dismissAllReviewBtn = document.getElementById('dismissAllReviewBtn');

// Engine Badge & Settings Modal
const engineStatusBadge = document.getElementById('engineStatusBadge');
const engineBadgeText = document.getElementById('engineBadgeText');
const engineHint = document.getElementById('engineHint');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const settingsModal = document.getElementById('settingsModal');
const apiKeyInput = document.getElementById('apiKeyInput');
const modelSelect = document.getElementById('modelSelect');
const toggleKeyVisibilityBtn = document.getElementById('toggleKeyVisibilityBtn');
const testKeyBtn = document.getElementById('testKeyBtn');
const saveKeyBtn = document.getElementById('saveKeyBtn');
const removeKeyBtn = document.getElementById('removeKeyBtn');
const keyTestResult = document.getElementById('keyTestResult');

let serverHasKey = false;

// Initialize Engine Status
initSettings();

async function initSettings() {
  const savedKey = localStorage.getItem(STORAGE_KEY_ANTHROPIC) || '';
  const savedModel = localStorage.getItem(STORAGE_KEY_MODEL) || 'claude-haiku-4-5-20251001';

  if (apiKeyInput) apiKeyInput.value = savedKey;
  if (modelSelect) modelSelect.value = savedModel;

  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      serverHasKey = Boolean(data.has_server_key);
    }
  } catch (e) {
    console.warn("Could not reach /api/status", e);
  }

  updateEngineBadge(savedKey, savedModel);
}

function updateEngineBadge(key, model) {
  const hasKey = (key && key.trim().startsWith('sk-ant-')) || serverHasKey;
  if (hasKey) {
    engineStatusBadge.className = 'engine-badge active';
    const modelShort = model.includes('opus') ? 'Claude Opus 4.5' : (model.includes('sonnet') ? 'Claude Sonnet 4.5' : 'Claude Haiku 4.5');
    engineBadgeText.innerText = `${modelShort} Active`;
    if (engineHint) {
      engineHint.innerHTML = `<span><strong>${modelShort}</strong> active</span>`;
    }
  } else {
    engineStatusBadge.className = 'engine-badge warning';
    engineBadgeText.innerText = 'Local Mode';
    if (engineHint) {
      engineHint.innerHTML = `<span>Upload PDF to extract transactions</span>`;
    }
  }
}

// Modal Event Listeners
openSettingsBtn.addEventListener('click', () => {
  keyTestResult.className = 'key-test-result hidden';
  keyTestResult.innerText = '';
  settingsModal.classList.remove('hidden');
});

closeSettingsBtn.addEventListener('click', () => {
  settingsModal.classList.add('hidden');
});

settingsModal.addEventListener('click', (e) => {
  if (e.target === settingsModal) {
    settingsModal.classList.add('hidden');
  }
});

engineStatusBadge.addEventListener('click', () => {
  openSettingsBtn.click();
});

toggleKeyVisibilityBtn.addEventListener('click', () => {
  if (apiKeyInput.type === 'password') {
    apiKeyInput.type = 'text';
    toggleKeyVisibilityBtn.innerText = 'Hide';
  } else {
    apiKeyInput.type = 'password';
    toggleKeyVisibilityBtn.innerText = 'Show';
  }
});

saveKeyBtn.addEventListener('click', () => {
  const key = apiKeyInput.value.trim();
  const model = modelSelect.value;
  if (key) {
    localStorage.setItem(STORAGE_KEY_ANTHROPIC, key);
  } else {
    localStorage.removeItem(STORAGE_KEY_ANTHROPIC);
  }
  localStorage.setItem(STORAGE_KEY_MODEL, model);
  updateEngineBadge(key, model);
  settingsModal.classList.add('hidden');
});

removeKeyBtn.addEventListener('click', () => {
  apiKeyInput.value = '';
  localStorage.removeItem(STORAGE_KEY_ANTHROPIC);
  updateEngineBadge('', modelSelect.value);
  keyTestResult.className = 'key-test-result';
  keyTestResult.innerText = 'API key cleared.';
});

testKeyBtn.addEventListener('click', async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    keyTestResult.className = 'key-test-result error';
    keyTestResult.innerText = 'Please enter an Anthropic API Key starting with sk-ant-';
    return;
  }

  testKeyBtn.disabled = true;
  testKeyBtn.innerText = 'Testing...';
  keyTestResult.className = 'key-test-result hidden';

  try {
    const res = await fetch('/api/test-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    const data = await res.json();
    if (data.success) {
      keyTestResult.className = 'key-test-result success';
      keyTestResult.innerText = `Connected: API key is valid.`;
    } else {
      keyTestResult.className = 'key-test-result error';
      keyTestResult.innerText = `Connection error: ${data.error || 'Invalid API Key'}`;
    }
  } catch (err) {
    keyTestResult.className = 'key-test-result error';
    keyTestResult.innerText = `Server error: Could not reach test endpoint. Make sure server.py is running.`;
  } finally {
    testKeyBtn.disabled = false;
    testKeyBtn.innerText = 'Test Connection';
  }
});

// Upload Listeners
browseBtn.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
  if (e.target.files && e.target.files[0]) {
    handleFileUpload(e.target.files[0]);
  }
});

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

// Filter Tabs Listeners
tabAll.addEventListener('click', () => {
  currentFilter = 'all';
  tabAll.classList.add('active');
  tabNeedsReview.classList.remove('active');
  renderTableOnly();
});

tabNeedsReview.addEventListener('click', () => {
  currentFilter = 'needs_review';
  tabNeedsReview.classList.add('active');
  tabAll.classList.remove('active');
  renderTableOnly();
});

statReviewBox.addEventListener('click', () => {
  tabNeedsReview.click();
});

dismissAllReviewBtn.addEventListener('click', () => {
  currentTransactions.forEach(t => {
    t.needs_review = false;
    if (t.confidence < 90) t.confidence = 92;
  });
  renderView();
});

addRowBtn.addEventListener('click', () => {
  const today = new Date();
  const d = String(today.getDate()).padStart(2, '0');
  const m = String(today.getMonth() + 1).padStart(2, '0');
  const y = today.getFullYear();
  currentTransactions.push({
    date: `${d}/${m}/${y}`,
    description: "New Transaction",
    debit: "0.00",
    credit: "",
    confidence: 100,
    confidence_level: 'high',
    needs_review: false,
    review_reason: null
  });
  renderView();
});

clearBtn.addEventListener('click', () => {
  currentTransactions = [];
  currentValidation = null;
  fileInput.value = '';
  reviewSection.classList.add('hidden');
  hideError();
});

searchInput.addEventListener('input', () => {
  renderTableOnly();
});

exportCsvBtn.addEventListener('click', () => {
  const csv = generateCsv(currentTransactions, false);
  downloadCsv(csv, 'standard');
});

exportAuditCsvBtn.addEventListener('click', () => {
  const csv = generateCsv(currentTransactions, true);
  downloadCsv(csv, 'audit');
});

copyBtn.addEventListener('click', () => {
  const csv = generateCsv(currentTransactions, false);
  navigator.clipboard.writeText(csv).then(() => {
    const origText = copyBtn.innerText;
    copyBtn.innerText = "Copied!";
    copyBtn.style.backgroundColor = "#10b981";
    copyBtn.style.color = "#ffffff";
    setTimeout(() => {
      copyBtn.innerText = origText;
      copyBtn.style.backgroundColor = "";
      copyBtn.style.color = "";
    }, 1500);
  });
});

function downloadCsv(csv, type) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const timestamp = new Date().toISOString().slice(0, 10);
  a.href = url;
  a.download = `statement_${type}_export_${timestamp}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function showLoading(show, message) {
  if (show) {
    if (message) loadingText.innerText = message;
    loadingIndicator.classList.remove('hidden');
  } else {
    loadingIndicator.classList.add('hidden');
  }
}

function showError(title, msg) {
  errorTitle.innerText = title;
  errorMessage.innerText = msg;
  errorBanner.classList.remove('hidden');
  reviewSection.classList.add('hidden');
}

function hideError() {
  errorBanner.classList.add('hidden');
}

async function handleFileUpload(file) {
  hideError();
  const apiKey = localStorage.getItem(STORAGE_KEY_ANTHROPIC) || '';
  const model = localStorage.getItem(STORAGE_KEY_MODEL) || 'claude-3-7-sonnet-20250219';

  showLoading(true, `Extracting statement transactions...`);

  // 1. Send to Backend API
  try {
    const formData = new FormData();
    formData.append('file', file);

    const headers = {};
    if (apiKey) {
      headers['X-Anthropic-Api-Key'] = apiKey;
      headers['X-Anthropic-Model'] = model;
    }

    const response = await fetch('/api/parse', {
      method: 'POST',
      headers: headers,
      body: formData
    });

    if (response.ok) {
      const data = await response.json();
      if (data.success && data.transactions && data.transactions.length > 0) {
        currentTransactions = data.transactions;
        currentValidation = data.validation;
        renderView();
        showLoading(false);
        return;
      } else if (data.error) {
        showError("Extraction Failed", data.error);
        showLoading(false);
        return;
      }
    }
  } catch (err) {
    console.warn("Backend API not reachable, running client-side PDF extraction engine...", err);
  }

  // 2. Client-side PDF.js extraction fallback
  if (window.pdfjsLib) {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      const parsed = await extractWithPdfJs(pdf);
      
      if (parsed.transactions && parsed.transactions.length > 0) {
        currentTransactions = parsed.transactions;
        currentValidation = parsed.validation;
        renderView();
        showLoading(false);
        return;
      } else {
        showError(
          "No Valid Transactions Detected",
          "Could not detect transaction rows in this PDF. Add your Anthropic API Key in Settings for high-accuracy visual statement parsing."
        );
        showLoading(false);
        return;
      }
    } catch (clientErr) {
      console.error("Client extraction error:", clientErr);
      showError("PDF Parsing Error", "Failed to parse PDF: " + clientErr.message);
      showLoading(false);
      return;
    }
  }

  showError(
    "Server Connection Required",
    "Please make sure the server is running at http://localhost:8080"
  );
  showLoading(false);
}

// Client-side PDF.js fallback parser
async function extractWithPdfJs(pdf) {
  const MONTH_MAP = {
    jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
    jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12'
  };
  const MONTH_REGEX_STR = '(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)';

  let allLines = [];
  let fullTextAccum = "";

  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
    const page = await pdf.getPage(pageNum);
    const content = await page.getTextContent();
    
    const items = content.items.map(item => ({
      str: item.str.trim(),
      x: item.transform[4],
      y: item.transform[5]
    })).filter(it => it.str.length > 0);

    items.sort((a, b) => {
      if (Math.abs(b.y - a.y) > 4) return b.y - a.y;
      return a.x - b.x;
    });

    let curLine = [];
    let curY = null;

    for (const it of items) {
      if (curY === null) {
        curY = it.y;
        curLine.push(it);
      } else if (Math.abs(it.y - curY) <= 5) {
        curLine.push(it);
      } else {
        curLine.sort((a, b) => a.x - b.x);
        allLines.push(curLine.map(t => t.str).join(' '));
        curLine = [it];
        curY = it.y;
      }
    }
    if (curLine.length > 0) {
      curLine.sort((a, b) => a.x - b.x);
      allLines.push(curLine.map(t => t.str).join(' '));
    }
    fullTextAccum += " \n " + allLines.join(' ');
  }

  let year = "2026";
  const yearM = fullTextAccum.match(/Statement (?:Period|Date).*?(\d{4})/i) || fullTextAccum.match(/\b(202[0-9])\b/);
  if (yearM) year = yearM[1];

  let expDebits = null;
  const debM = fullTextAccum.match(/(?:Purchases\/charges\s*\+|SUB-TOTAL\s+DEBITS.*?)\s*\$?\s*([\d,]+\.\d{2})/i);
  if (debM) expDebits = parseFloat(debM[1].replace(/,/g, ''));

  let expCredits = null;
  const credM = fullTextAccum.match(/(?:Payments\/credits\s*-|SUB-TOTAL\s+CREDITS.*?)\s*\$?\s*([\d,]+\.\d{2})/i);
  if (credM) expCredits = parseFloat(credM[1].replace(/,/g, ''));

  const rowRegex = new RegExp(
    `^(?:(\\d{3,4})\\s+)?(${MONTH_REGEX_STR}\\s+\\d{1,2}|\\d{1,2}[/\\-.]\\d{1,2}(?:[/\\-.]\\d{2,4})?)\\s+(?:(${MONTH_REGEX_STR}\\s+\\d{1,2}|\\d{1,2}[/\\-.]\\d{1,2})\\s+)?(.*)$`,
    'i'
  );
  const amountRegex = /(\$?\s*[\d,]+\.\d{2})(-|CR)?$/i;

  const startKeywords = ['TRANSACTIONS SINCE', 'TRANSACTIONS - CONTINUED', 'TRANSACTIONS', 'ACCOUNT ACTIVITY', 'DETAILS OF YOUR TRANSACTIONS'];
  const endKeywords = ['SUB-TOTAL', 'SUB TOTAL', 'TOTAL DEBITS', 'TOTAL CREDITS', 'INTEREST CHARGES', 'ACCOUNT SUMMARY'];

  let inTx = false;
  const extracted = [];
  let curTx = null;

  for (const rawLine of allLines) {
    const line = rawLine.trim();
    const upper = line.toUpperCase();

    if (startKeywords.some(k => upper.includes(k))) {
      inTx = true;
      if (curTx && curTx.amount) extracted.push(curTx);
      curTx = null;
      continue;
    }
    if (inTx && endKeywords.some(k => upper.startsWith(k))) {
      if (curTx && curTx.amount) extracted.push(curTx);
      curTx = null;
      inTx = false;
      continue;
    }

    if (!inTx) {
      if (rowRegex.test(line) && amountRegex.test(line)) inTx = true;
      else continue;
    }

    if (/^(REF\.?#|TRANS\.?\s*DATE|POST\s*DATE|DETAILS|AMOUNT|ACCOUNT|CARDMEMBER)/i.test(upper)) continue;
    if (/^[A-Z\s\-]+-\s*\d{4}\s*X+/i.test(upper)) continue;
    if (upper.startsWith('CONTINUED ON PAGE')) {
      if (curTx && curTx.amount) extracted.push(curTx);
      curTx = null;
      continue;
    }

    const m = line.match(rowRegex);
    if (m) {
      if (curTx && curTx.amount) extracted.push(curTx);
      const rawDate = m[2];
      let formattedDate = rawDate;
      const monthPart = rawDate.match(new RegExp(MONTH_REGEX_STR, 'i'));
      if (monthPart) {
        const monStr = monthPart[0].toLowerCase().slice(0, 3);
        const dayStr = rawDate.replace(new RegExp(MONTH_REGEX_STR, 'i'), '').trim();
        const mon = MONTH_MAP[monStr] || '01';
        const day = String(parseInt(dayStr, 10)).padStart(2, '0');
        formattedDate = `${day}/${mon}/${year}`;
      }

      const rest = (m[4] || '').trim();
      curTx = {
        date: formattedDate,
        descLines: [],
        amount: null,
        isCredit: false,
        hasRef: Boolean(m[1])
      };

      const amtM = rest.match(amountRegex);
      if (amtM) {
        curTx.amount = amtM[1].replace(/[$\s]/g, '');
        curTx.isCredit = Boolean(amtM[2]);
        const d = rest.slice(0, amtM.index).trim();
        if (d) curTx.descLines.push(d);
      } else if (rest) {
        curTx.descLines.push(rest);
      }
    } else if (curTx) {
      const amtM = line.match(amountRegex);
      if (amtM && !curTx.amount) {
        curTx.amount = amtM[1].replace(/[$\s]/g, '');
        curTx.isCredit = Boolean(amtM[2]);
        const d = line.slice(0, amtM.index).trim();
        if (d) curTx.descLines.push(d);
        extracted.push(curTx);
        curTx = null;
      } else {
        if (!/^(page\s+\d+|scotiabank|continued)/i.test(line)) {
          curTx.descLines.push(line);
        }
      }
    }
  }
  if (curTx && curTx.amount) extracted.push(curTx);

  let calcDebits = 0;
  let calcCredits = 0;
  let needsRevCount = 0;
  let totalConfidence = 0;

  const resultRows = extracted.map(tx => {
    const desc = tx.descLines.join(' ').replace(/\s+/g, ' ').trim();
    const val = parseFloat(tx.amount.replace(/,/g, '')) || 0;
    
    let conf = 88;
    const reasons = [];
    if (!tx.hasRef) conf -= 5;
    if (tx.descLines.length > 2) {
      conf -= 8;
      reasons.push("Multi-line description combined");
    }
    if (/\b(refund|payment|cr)\b/i.test(desc) && !tx.isCredit) {
      conf -= 15;
      reasons.push("Payment/refund keyword classified as debit");
    }

    conf = Math.max(45, Math.min(95, conf));
    totalConfidence += conf;
    const needsRev = conf < 85 || reasons.length > 0;
    if (needsRev) needsRevCount++;

    if (tx.isCredit) {
      calcCredits += val;
      return {
        date: tx.date,
        description: desc,
        debit: '',
        credit: val.toFixed(2),
        confidence: conf,
        confidence_level: conf >= 90 ? 'high' : (conf >= 75 ? 'medium' : 'low'),
        needs_review: needsRev,
        review_reason: reasons.join('; ') || null
      };
    } else {
      calcDebits += val;
      return {
        date: tx.date,
        description: desc,
        debit: val.toFixed(2),
        credit: '',
        confidence: conf,
        confidence_level: conf >= 90 ? 'high' : (conf >= 75 ? 'medium' : 'low'),
        needs_review: needsRev,
        review_reason: reasons.join('; ') || null
      };
    }
  });

  const avgConf = resultRows.length ? Math.round(totalConfidence / resultRows.length) : 0;
  const messages = [];
  let reconciled = true;
  if (expDebits !== null) {
    if (Math.abs(calcDebits - expDebits) <= 0.01) {
      messages.push(`Debits match statement summary: $${calcDebits.toFixed(2)}`);
    } else {
      reconciled = false;
      messages.push(`Debit mismatch: Extracted $${calcDebits.toFixed(2)} vs Statement Summary $${expDebits.toFixed(2)}`);
    }
  }
  if (expCredits !== null) {
    if (Math.abs(calcCredits - expCredits) <= 0.01) {
      messages.push(`Credits match statement summary: $${calcCredits.toFixed(2)}`);
    } else {
      reconciled = false;
      messages.push(`Credit mismatch: Extracted $${calcCredits.toFixed(2)} vs Statement Summary ${expCredits.toFixed(2)}`);
    }
  }

  return {
    transactions: resultRows,
    validation: {
      engine: 'Local Parser',
      status: reconciled && (expDebits !== null || expCredits !== null) ? 'reconciled' : (reconciled ? 'verified' : 'warning'),
      reconciled,
      overall_confidence: avgConf,
      needs_review_count: needsRevCount,
      total_debits: calcDebits.toFixed(2),
      total_credits: calcCredits.toFixed(2),
      expected_debits: expDebits ? expDebits.toFixed(2) : null,
      expected_credits: expCredits ? expCredits.toFixed(2) : null,
      messages: messages.length ? messages : [`Extracted ${resultRows.length} transactions`]
    }
  };
}

function renderView() {
  renderValidation();
  recalcStats();
  renderTableOnly();
  reviewSection.classList.remove('hidden');
}

function renderValidation() {
  if (!currentValidation) {
    validationBanner.classList.add('hidden');
    return;
  }
  validationBanner.classList.remove('hidden', 'alert-success', 'alert-warning', 'alert-danger');

  if (currentValidation.status === 'reconciled') {
    validationBanner.classList.add('alert-success');
    validationIcon.innerText = '';
    validationTitle.innerText = 'Reconciliation Verified';
  } else if (currentValidation.status === 'warning') {
    validationBanner.classList.add('alert-warning');
    validationIcon.innerText = '';
    validationTitle.innerText = 'Review Recommended';
  } else {
    validationBanner.classList.add('alert-success');
    validationIcon.innerText = '';
    validationTitle.innerText = 'Statement Extraction Complete';
  }

  if (extractionEngineTag) {
    extractionEngineTag.innerText = currentValidation.engine || 'Parser';
  }

  validationList.innerHTML = '';
  (currentValidation.messages || []).forEach(msg => {
    const li = document.createElement('li');
    li.innerText = msg;
    validationList.appendChild(li);
  });

  if (currentValidation.expected_debits) {
    statExpectedDebits.innerText = `Statement: $${currentValidation.expected_debits}`;
  } else {
    statExpectedDebits.innerText = `No summary subtotal`;
  }
  if (currentValidation.expected_credits) {
    statExpectedCredits.innerText = `Statement: $${currentValidation.expected_credits}`;
  } else {
    statExpectedCredits.innerText = `No summary subtotal`;
  }
}

function renderTableOnly() {
  const query = (searchInput.value || '').toLowerCase().trim();
  tableBody.innerHTML = '';

  let totalDebits = 0;
  let totalCredits = 0;

  currentTransactions.forEach((tx, index) => {
    const isNeedsReview = Boolean(tx.needs_review);

    // Tab filter: all vs needs_review
    if (currentFilter === 'needs_review' && !isNeedsReview) {
      return;
    }

    const matchesSearch = !query || 
      (tx.date && tx.date.toLowerCase().includes(query)) ||
      (tx.description && tx.description.toLowerCase().includes(query)) ||
      (tx.debit && tx.debit.includes(query)) ||
      (tx.credit && tx.credit.includes(query));

    if (!matchesSearch) return;

    const dVal = parseFloat(String(tx.debit).replace(/,/g, '')) || 0;
    const cVal = parseFloat(String(tx.credit).replace(/,/g, '')) || 0;
    totalDebits += dVal;
    totalCredits += cVal;

    const conf = tx.confidence !== undefined ? tx.confidence : 95;
    const confLevel = conf >= 90 ? 'high' : (conf >= 75 ? 'medium' : 'low');
    const rowClass = isNeedsReview ? 'row-needs-review' : '';

    const tr = document.createElement('tr');
    tr.className = rowClass;
    tr.innerHTML = `
      <td style="color: #94a3b8; font-size: 0.8rem;">${index + 1}</td>
      <td>
        <div class="cell-edit" contenteditable="true" data-field="date" data-index="${index}">${escapeHtml(tx.date)}</div>
      </td>
      <td>
        <div class="cell-edit" contenteditable="true" data-field="description" data-index="${index}">${escapeHtml(tx.description)}</div>
      </td>
      <td style="text-align: right;">
        <div class="cell-edit amount-debit" contenteditable="true" data-field="debit" data-index="${index}">${escapeHtml(tx.debit)}</div>
      </td>
      <td style="text-align: right;">
        <div class="cell-edit amount-credit" contenteditable="true" data-field="credit" data-index="${index}">${escapeHtml(tx.credit)}</div>
      </td>
      <td style="text-align: center;">
        <div class="confidence-wrapper">
          <span class="confidence-pill ${confLevel}" title="${conf}% confidence">${conf}%</span>
          ${isNeedsReview ? `
            <span class="review-badge" title="${escapeHtml(tx.review_reason || 'Flagged for review')}">
              Review
            </span>
            <button class="btn-approve-sm" data-approve-index="${index}" title="Approve row and clear review flag">Approve</button>
          ` : `
            <span style="color: #10b981; font-size: 0.75rem; font-weight: 600;">Verified</span>
          `}
        </div>
      </td>
      <td style="text-align: center;">
        <button class="btn-del" title="Delete Row" data-delete-index="${index}">&times;</button>
      </td>
    `;
    tableBody.appendChild(tr);
  });

  // Cell editing listeners
  tableBody.querySelectorAll('.cell-edit').forEach(cell => {
    cell.addEventListener('blur', (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      const field = e.target.dataset.field;
      currentTransactions[idx][field] = e.target.innerText.trim();
      recalcStats();
    });
  });

  // Approve button listeners
  tableBody.querySelectorAll('.btn-approve-sm').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.target.dataset.approveIndex, 10);
      if (currentTransactions[idx]) {
        currentTransactions[idx].needs_review = false;
        if (currentTransactions[idx].confidence < 90) {
          currentTransactions[idx].confidence = 92;
        }
        recalcStats();
        renderTableOnly();
      }
    });
  });

  // Delete button listeners
  tableBody.querySelectorAll('.btn-del').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.target.dataset.deleteIndex, 10);
      currentTransactions.splice(idx, 1);
      recalcStats();
      renderTableOnly();
    });
  });
}

function recalcStats() {
  let totalDebits = 0;
  let totalCredits = 0;
  let totalConf = 0;
  let needsRevCount = 0;

  currentTransactions.forEach(tx => {
    totalDebits += parseFloat(String(tx.debit).replace(/,/g, '')) || 0;
    totalCredits += parseFloat(String(tx.credit).replace(/,/g, '')) || 0;
    const conf = tx.confidence !== undefined ? tx.confidence : 95;
    totalConf += conf;
    if (tx.needs_review) needsRevCount++;
  });

  const avgConf = currentTransactions.length ? Math.round(totalConf / currentTransactions.length) : 100;

  statCount.innerText = currentTransactions.length;
  statDebits.innerText = `$${totalDebits.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  statCredits.innerText = `$${totalCredits.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  statConfidence.innerText = `${avgConf}%`;
  statConfidence.className = `stat-val ${avgConf >= 90 ? 'confidence-high' : (avgConf >= 75 ? 'stat-val warning' : 'stat-val debit')}`;

  statNeedsReview.innerText = needsRevCount;
  statNeedsReview.className = `stat-val ${needsRevCount > 0 ? 'warning' : 'credit'}`;

  // Tab counts
  countAll.innerText = currentTransactions.length;
  countReview.innerText = needsRevCount;

  if (needsRevCount > 0) {
    tabNeedsReview.classList.add('has-items');
    reviewNoticeBanner.classList.remove('hidden');
    reviewNoticeCount.innerText = needsRevCount;
  } else {
    tabNeedsReview.classList.remove('has-items');
    reviewNoticeBanner.classList.add('hidden');
  }
}

function generateCsv(txs, includeConfidence) {
  if (includeConfidence) {
    const rows = [
      ['Date', 'Description', 'Debit', 'Credit', 'Confidence', 'Needs Review', 'Review Reason']
    ];
    txs.forEach(t => {
      rows.push([
        `"${(t.date || '').replace(/"/g, '""')}"`,
        `"${(t.description || '').replace(/"/g, '""')}"`,
        t.debit ? `"${t.debit}"` : '',
        t.credit ? `"${t.credit}"` : '',
        `"${t.confidence || 95}%"`,
        t.needs_review ? '"YES"' : '"NO"',
        `"${(t.review_reason || '').replace(/"/g, '""')}"`
      ]);
    });
    return rows.map(r => r.join(',')).join('\r\n');
  } else {
    const rows = [
      ['Date', 'Description', 'Debit', 'Credit']
    ];
    txs.forEach(t => {
      rows.push([
        `"${(t.date || '').replace(/"/g, '""')}"`,
        `"${(t.description || '').replace(/"/g, '""')}"`,
        t.debit ? `"${t.debit}"` : '',
        t.credit ? `"${t.credit}"` : ''
      ]);
    });
    return rows.map(r => r.join(',')).join('\r\n');
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
