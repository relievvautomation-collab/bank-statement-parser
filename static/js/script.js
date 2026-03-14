// Global variables
let selectedFile = null;
let extractedData = {
    bank: '',
    format: '',
    metadata: {
        bank_name: '',
        account_holder: '',
        account_number: '',
        from_date: '',
        to_date: ''
    },
    transactions: [],
    processingStats: {
        startTime: 0,
        endTime: 0,
        pageCount: 0
    },
    original_filename: ''
};

// PDF.js variables
let pdfDocument = null;
let currentPage = 1;
let totalPages = 0;

// User data storage
let userData = {
    totalFilesProcessed: 0,
    todayFilesProcessed: 0,
    lastResetDate: new Date().toDateString()
};

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const browseButton = document.getElementById('browseButton');
const fileInput = document.getElementById('fileInput');
const fileCountEl = document.getElementById('fileCount');
const summaryFileCount = document.getElementById('summaryFileCount');
const summaryTransactionCount = document.getElementById('summaryTransactionCount');
const parseBtn = document.getElementById('parseBtn');
const resetBtn = document.getElementById('resetBtn');
const downloadBtn = document.getElementById('downloadBtn');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const pdfViewer = document.getElementById('pdfViewer');
const pdfInfo = document.getElementById('pdfInfo');
const pdfControls = document.getElementById('pdfControls');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageInfo = document.getElementById('pageInfo');
const excelTable = document.getElementById('excelTable');
const excelBody = document.getElementById('excelBody');
const excelHeader = document.getElementById('excelHeader');
const excelInfo = document.getElementById('excelInfo');
const excelRowInfo = document.getElementById('excelRowInfo');
const previewTabs = document.querySelectorAll('.preview-tab');
const tabPanes = document.querySelectorAll('.tab-pane');
const infoTabs = document.querySelectorAll('.info-tab');
const tabPanesInfo = document.querySelectorAll('.tab-pane-info');
const reportModal = document.getElementById('reportModal');
const closeModal = document.getElementById('closeModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const confirmDownload = document.getElementById('confirmDownload');
const modalPageCount = document.getElementById('modalPageCount');
const modalTransactionCount = document.getElementById('modalTransactionCount');
const modalTime = document.getElementById('modalTime');
const modalFileSize = document.getElementById('modalFileSize');
const totalFilesCounter = document.getElementById('totalFilesCounter');
const todayFilesCounter = document.getElementById('todayFilesCounter');
const currentDate = document.getElementById('currentDate');
const transactionCounter = document.getElementById('transactionCounter');
const counterValue = document.getElementById('counterValue');
const bankInfo = document.getElementById('bankInfo');
const bankName = document.getElementById('bankName');
const accountHolder = document.getElementById('accountHolder');
const accountNumber = document.getElementById('accountNumber');
const statementPeriod = document.getElementById('statementPeriod');
const statsContainer = document.getElementById('statsContainer');

// Initialize
function init() {
    loadUserData();
    setupEventListeners();
    updateCurrentDate();
    setupScrollListener();
}

function loadUserData() {
    const savedData = localStorage.getItem('bankStatementToolData');
    if (savedData) {
        userData = JSON.parse(savedData);
        const today = new Date().toDateString();
        if (userData.lastResetDate !== today) {
            userData.todayFilesProcessed = 0;
            userData.lastResetDate = today;
            saveUserData();
        }
    }
    updateStatisticsCounters();
}

function saveUserData() {
    localStorage.setItem('bankStatementToolData', JSON.stringify(userData));
    updateStatisticsCounters();
}

function updateStatisticsCounters() {
    totalFilesCounter.textContent = userData.totalFilesProcessed.toLocaleString();
    todayFilesCounter.textContent = userData.todayFilesProcessed.toLocaleString();
}

function updateCurrentDate() {
    const now = new Date();
    const options = { day: 'numeric', month: 'long', year: 'numeric', weekday: 'long' };
    currentDate.textContent = now.toLocaleDateString('en-IN', options);
}

function setupScrollListener() {
    let lastScrollTop = 0;
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        if (scrollTop > 100 && scrollTop > lastScrollTop) {
            statsContainer.classList.add('visible');
        } else if (scrollTop <= 100) {
            statsContainer.classList.remove('visible');
        }
        lastScrollTop = scrollTop;
    });
}

function setupEventListeners() {
    browseButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    });
    uploadArea.addEventListener('click', function(e) {
        if (e.target.closest('#browseButton')) return;
        fileInput.click();
    });
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
    parseBtn.addEventListener('click', parsePDF);
    resetBtn.addEventListener('click', resetTool);
    downloadBtn.addEventListener('click', showDownloadModal);
    closeModal.addEventListener('click', () => { reportModal.style.display = 'none'; });
    closeModalBtn.addEventListener('click', () => { reportModal.style.display = 'none'; });
    confirmDownload.addEventListener('click', downloadExcelFile);
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) { currentPage--; renderPDFPage(currentPage); }
    });
    nextPageBtn.addEventListener('click', () => {
        if (currentPage < totalPages) { currentPage++; renderPDFPage(currentPage); }
    });
    previewTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            previewTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `${tabId}-preview`) pane.classList.add('active');
            });
        });
    });
    infoTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            infoTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            tabPanesInfo.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === `${tabId}-tab`) pane.classList.add('active');
            });
        });
    });
}

function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showNotification('Please select a PDF file.', 'error');
        return;
    }
    selectedFile = file;
    updateFileCount();
    extractedData = {
        bank: '', format: '',
        metadata: { bank_name: '', account_holder: '', account_number: '', from_date: '', to_date: '' },
        transactions: [],
        processingStats: { startTime: 0, endTime: 0, pageCount: 0 },
        original_filename: ''
    };
    parseBtn.disabled = false;
    previewTabs[0].click();
    loadPDF(file);
    pdfInfo.textContent = `File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
}

async function loadPDF(file) {
    try {
        const arrayBuffer = await file.arrayBuffer();
        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        pdfDocument = await loadingTask.promise;
        totalPages = pdfDocument.numPages;
        extractedData.processingStats.pageCount = totalPages;
        pdfControls.style.display = 'flex';
        currentPage = 1;
        renderPDFPage(1);
    } catch (error) {
        console.error('Error loading PDF:', error);
        showNotification('Error loading PDF file. Please ensure it\'s a valid bank statement PDF.', 'error');
        pdfViewer.innerHTML = `<div style="text-align: center; padding: 4rem; color: var(--text-light);">
            <i class="fas fa-exclamation-triangle" style="font-size: 4rem; margin-bottom: 1.5rem; display: block; color: var(--warning-orange);"></i>
            <h3 style="margin-bottom: 0.8rem; color: var(--primary-blue);">Error Loading PDF</h3>
            <p>Please ensure you've uploaded a valid bank statement PDF.</p>
        </div>`;
    }
}

async function renderPDFPage(pageNumber) {
    try {
        const page = await pdfDocument.getPage(pageNumber);
        const viewport = page.getViewport({ scale: 1.2 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        canvas.className = 'pdf-canvas-container';
        pdfViewer.innerHTML = '';
        pdfViewer.appendChild(canvas);
        await page.render({ canvasContext: context, viewport: viewport }).promise;
        pageInfo.textContent = `Page ${pageNumber} of ${totalPages}`;
        prevPageBtn.disabled = pageNumber <= 1;
        nextPageBtn.disabled = pageNumber >= totalPages;
    } catch (error) {
        console.error('Error rendering PDF page:', error);
        showNotification('Error rendering PDF page.', 'error');
    }
}

function updateFileCount() {
    fileCountEl.textContent = selectedFile ? '1' : '0';
    summaryFileCount.textContent = selectedFile ? '1' : '0';
}

async function parsePDF() {
    if (!selectedFile) {
        showNotification('Please select a bank statement PDF file first.', 'error');
        return;
    }
    extractedData.processingStats.startTime = Date.now();
    parseBtn.innerHTML = '<div class="loading"></div> Parsing Bank Statement...';
    parseBtn.disabled = true;
    downloadBtn.disabled = true;
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('original_filename', selectedFile.name);
        progressFill.style.width = '30%';
        const response = await fetch('/upload', { method: 'POST', body: formData });
        progressFill.style.width = '70%';
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const result = await response.json();
        progressFill.style.width = '100%';
        if (result.success) {
            extractedData.bank = result.bank;
            extractedData.format = result.format;
            extractedData.metadata = result.metadata;
            extractedData.transactions = result.transactions;
            extractedData.processingStats.endTime = Date.now();
            extractedData.processingStats.pageCount = result.metadata.page_count || totalPages;
            extractedData.original_filename = result.original_filename;
            updateSummary();
            updateBankInfo();
            updateExcelPreview();
            transactionCounter.style.display = 'flex';
            counterValue.textContent = extractedData.transactions.length;
            downloadBtn.disabled = false;
            previewTabs[1].click();
            showNotification(`Successfully parsed ${extractedData.transactions.length} transactions from ${extractedData.bank} statement`, 'success');
        } else {
            throw new Error(result.error || 'Unknown error from server');
        }
    } catch (error) {
        console.error('Error parsing PDF:', error);
        showNotification('Error parsing PDF: ' + error.message, 'error');
    } finally {
        parseBtn.innerHTML = '<i class="fas fa-cogs"></i> Parse Bank Statement';
        parseBtn.disabled = false;
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }
}

function updateSummary() {
    summaryTransactionCount.textContent = extractedData.transactions.length;
}

function updateBankInfo() {
    if (extractedData.metadata && 
        (extractedData.metadata.bank_name || extractedData.metadata.account_holder || extractedData.metadata.account_number)) {
        bankInfo.classList.add('visible');
        bankInfo.style.display = 'block';
        bankName.textContent = extractedData.metadata.bank_name || extractedData.bank || 'Not Available';
        accountHolder.textContent = extractedData.metadata.account_holder || 'Not Available';
        accountNumber.textContent = extractedData.metadata.account_number || 'Not Available';
        const period = `${extractedData.metadata.from_date || ''} to ${extractedData.metadata.to_date || ''}`;
        statementPeriod.textContent = period.trim() !== 'to' ? period : 'Not Available';
    }
}

function formatIndianCurrency(amount) {
    if (amount === undefined || amount === null || amount === '') return '0.00';
    const num = parseFloat(amount);
    if (isNaN(num)) return '0.00';
    return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function updateExcelPreview() {
    if (extractedData.transactions.length === 0) {
        excelBody.innerHTML = `<tr>
            <td colspan="8" style="text-align: center; padding: 4rem; color: var(--text-light);">
                <i class="fas fa-file-excel" style="font-size: 3rem; margin-bottom: 1rem; display: block;"></i>
                <h3 style="margin-bottom: 0.5rem; color: var(--primary-blue);">No Data to Display</h3>
                <p>Parse a bank statement PDF to see the extracted Excel data here</p>
            </td>
        </tr>`;
        excelInfo.textContent = 'No data parsed';
        excelRowInfo.textContent = 'Showing 0 rows';
        return;
    }
    let columns = [], dataKeys = [];
    if (extractedData.bank === 'SBI') {
        columns = ['Txn Date', 'Value Date', 'Description', 'Ref No./Cheque No.', 'Debit', 'Credit', 'Balance', 'Page No'];
        dataKeys = ['txn_date', 'value_date', 'description', 'ref_no', 'debit', 'credit', 'balance', 'page_no'];
    } else if (extractedData.bank === 'HDFC') {
        if (extractedData.format === 'format1') {
            columns = ['Date', 'Narration', 'Chq./Ref.No.', 'Value Dt', 'Withdrawal Amt.', 'Deposit Amt.', 'Closing Balance', 'Page No'];
            dataKeys = ['date', 'narration', 'chq_ref', 'value_date', 'withdrawal', 'deposit', 'closing_balance', 'page_no'];
        } else {
            columns = ['Txn Date', 'Narration', 'Withdrawals', 'Deposits', 'Closing Balance', 'Page No'];
            dataKeys = ['txn_date', 'narration', 'withdrawals', 'deposits', 'closing_balance', 'page_no'];
        }
    } else if (extractedData.bank === 'SCB') {
        columns = ['Date', 'Value Date', 'Description', 'Cheque', 'Deposit', 'Withdrawal', 'Balance', 'Page No'];
        dataKeys = ['date', 'value_date', 'description', 'cheque', 'deposit', 'withdrawal', 'balance', 'page_no'];
    }
    let headerHtml = '<tr>';
    columns.forEach(col => headerHtml += `<th>${col}</th>`);
    headerHtml += '</tr>';
    excelHeader.innerHTML = headerHtml;
    excelBody.innerHTML = '';
    const rowsToShow = extractedData.transactions.slice(0, 50);
    rowsToShow.forEach(txn => {
        const row = document.createElement('tr');
        let rowHtml = '';
        dataKeys.forEach(key => {
            let value = txn[key] !== undefined ? txn[key] : '';
            if (['debit', 'credit', 'balance', 'withdrawal', 'deposit', 'withdrawals', 'deposits', 'closing_balance'].includes(key)) {
                value = formatIndianCurrency(value);
                rowHtml += `<td style="text-align: right;">${value}</td>`;
            } else {
                rowHtml += `<td>${value}</td>`;
            }
        });
        row.innerHTML = rowHtml;
        excelBody.appendChild(row);
    });
    if (extractedData.transactions.length > 50) {
        const infoRow = document.createElement('tr');
        infoRow.innerHTML = `<td colspan="${columns.length}" style="text-align: center; padding: 1rem; background: var(--light-blue); color: var(--primary-blue); font-weight: 600;">
            <i class="fas fa-info-circle"></i> Showing first 50 of ${extractedData.transactions.length} transactions.
            <button onclick="showAllTransactions()" style="margin-left: 10px; padding: 5px 15px; background: var(--accent-blue); color: white; border: none; border-radius: 4px; cursor: pointer;">
                Show All
            </button>
            <br><small>Full data will be included in the downloaded file</small>
        </td>`;
        excelBody.appendChild(infoRow);
    }
    excelInfo.textContent = `Extracted ${extractedData.transactions.length} transactions from ${extractedData.bank} bank statement (${extractedData.format || 'standard'})`;
    excelRowInfo.textContent = `Showing ${Math.min(50, extractedData.transactions.length)} rows`;
}

window.showAllTransactions = function() {
    if (!extractedData.transactions.length) return;
    let columns = [], dataKeys = [];
    if (extractedData.bank === 'SBI') {
        columns = ['Txn Date', 'Value Date', 'Description', 'Ref No./Cheque No.', 'Debit', 'Credit', 'Balance', 'Page No'];
        dataKeys = ['txn_date', 'value_date', 'description', 'ref_no', 'debit', 'credit', 'balance', 'page_no'];
    } else if (extractedData.bank === 'HDFC') {
        if (extractedData.format === 'format1') {
            columns = ['Date', 'Narration', 'Chq./Ref.No.', 'Value Dt', 'Withdrawal Amt.', 'Deposit Amt.', 'Closing Balance', 'Page No'];
            dataKeys = ['date', 'narration', 'chq_ref', 'value_date', 'withdrawal', 'deposit', 'closing_balance', 'page_no'];
        } else {
            columns = ['Txn Date', 'Narration', 'Withdrawals', 'Deposits', 'Closing Balance', 'Page No'];
            dataKeys = ['txn_date', 'narration', 'withdrawals', 'deposits', 'closing_balance', 'page_no'];
        }
    } else if (extractedData.bank === 'SCB') {
        columns = ['Date', 'Value Date', 'Description', 'Cheque', 'Deposit', 'Withdrawal', 'Balance', 'Page No'];
        dataKeys = ['date', 'value_date', 'description', 'cheque', 'deposit', 'withdrawal', 'balance', 'page_no'];
    }
    excelBody.innerHTML = '';
    extractedData.transactions.forEach(txn => {
        const row = document.createElement('tr');
        let rowHtml = '';
        dataKeys.forEach(key => {
            let value = txn[key] !== undefined ? txn[key] : '';
            if (['debit', 'credit', 'balance', 'withdrawal', 'deposit', 'withdrawals', 'deposits', 'closing_balance'].includes(key)) {
                value = formatIndianCurrency(value);
                rowHtml += `<td style="text-align: right;">${value}</td>`;
            } else {
                rowHtml += `<td>${value}</td>`;
            }
        });
        row.innerHTML = rowHtml;
        excelBody.appendChild(row);
    });
    excelRowInfo.textContent = `Showing all ${extractedData.transactions.length} rows`;
};

function showDownloadModal() {
    if (extractedData.transactions.length === 0) {
        showNotification('No data to download. Please parse a bank statement PDF first.', 'error');
        return;
    }
    modalPageCount.textContent = extractedData.processingStats.pageCount || 1;
    modalTransactionCount.textContent = extractedData.transactions.length;
    const processingTime = ((extractedData.processingStats.endTime - extractedData.processingStats.startTime) / 1000).toFixed(2);
    modalTime.textContent = `${processingTime}s`;
    const estimatedSizeKB = Math.round((extractedData.transactions.length * 13 * 15) / 1024);
    modalFileSize.textContent = `${estimatedSizeKB} KB`;
    reportModal.style.display = 'flex';
}

async function downloadExcelFile() {
    if (extractedData.transactions.length === 0) {
        showNotification('No data to download.', 'error');
        return;
    }
    try {
        confirmDownload.innerHTML = '<div class="loading"></div> Generating Excel...';
        confirmDownload.disabled = true;
        const downloadData = {
            bank: extractedData.bank,
            format: extractedData.format,
            metadata: extractedData.metadata,
            transactions: extractedData.transactions,
            original_filename: extractedData.original_filename
        };
        const response = await fetch('/download_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(downloadData)
        });
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const result = await response.json();
        if (result.success) {
            const a = document.createElement('a');
            a.href = result.download_url;
            a.download = result.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            userData.totalFilesProcessed++;
            userData.todayFilesProcessed++;
            saveUserData();
            reportModal.style.display = 'none';
            showNotification('Excel file downloaded successfully!', 'success');
        } else {
            throw new Error(result.error || 'Failed to generate Excel file');
        }
    } catch (error) {
        console.error('Error downloading file:', error);
        showNotification('Error generating Excel file: ' + error.message, 'error');
    } finally {
        confirmDownload.innerHTML = '<i class="fas fa-download"></i> Download Excel File';
        confirmDownload.disabled = false;
    }
}

function resetTool() {
    selectedFile = null;
    pdfDocument = null;
    currentPage = 1;
    totalPages = 0;
    extractedData = {
        bank: '', format: '',
        metadata: { bank_name: '', account_holder: '', account_number: '', from_date: '', to_date: '' },
        transactions: [],
        processingStats: { startTime: 0, endTime: 0, pageCount: 0 },
        original_filename: ''
    };
    updateFileCount();
    summaryTransactionCount.textContent = '0';
    parseBtn.disabled = true;
    downloadBtn.disabled = true;
    progressBar.style.display = 'none';
    transactionCounter.style.display = 'none';
    counterValue.textContent = '0';
    bankInfo.classList.remove('visible');
    bankInfo.style.display = 'none';
    pdfControls.style.display = 'none';
    pdfViewer.innerHTML = `<div style="text-align: center; padding: 4rem; color: var(--accent-blue);">
        <i class="fas fa-file-pdf" style="font-size: 4rem; margin-bottom: 1.5rem; display: block; color: var(--border-blue);"></i>
        <h3 style="margin-bottom: 0.8rem; color: var(--primary-blue);">No PDF to Display</h3>
        <p>Upload a bank statement PDF to see the preview here</p>
    </div>`;
    pdfInfo.textContent = 'No PDF loaded. Upload a bank statement PDF to see preview.';
    excelHeader.innerHTML = '';
    excelBody.innerHTML = `<tr>
        <td colspan="8" style="text-align: center; padding: 4rem; color: var(--accent-blue);">
            <i class="fas fa-file-excel" style="font-size: 3rem; margin-bottom: 1rem; display: block;"></i>
            <h3 style="margin-bottom: 0.5rem; color: var(--primary-blue);">No Data to Display</h3>
            <p>Parse a bank statement PDF to see the extracted Excel data here</p>
        </td>
    </tr>`;
    excelInfo.textContent = 'No data parsed';
    excelRowInfo.textContent = 'Showing 0 rows';
    fileInput.value = '';
    previewTabs[0].click();
    showNotification('Tool has been reset successfully.', 'success');
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 1rem 1.5rem; border-radius: 8px;
        color: white; font-weight: 600; z-index: 9999; display: flex; align-items: center;
        gap: 0.8rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideIn 0.3s ease; max-width: 400px;
    `;
    if (type === 'success') notification.style.background = 'var(--success-green)';
    else if (type === 'error') notification.style.background = 'var(--error-red)';
    else notification.style.background = 'var(--accent-blue)';
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    notification.innerHTML = `<i class="fas fa-${icon}"></i><span>${message}</span>`;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => { if (notification.parentNode) notification.parentNode.removeChild(notification); }, 300);
    }, 5000);
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
        `;
        document.head.appendChild(style);
    }
}

document.addEventListener('DOMContentLoaded', init);
