// Global variables
let selectedEtf = "00997A"; // Default active ETF
let dashboardChartInstance = null;
let historyChartInstance = null;
let currentChartType = "portfolio"; // Default chart display type

const ETF_NAMES = {
    "00997A": "群益美國增長主動式ETF",
    "00981A": "統一台股增長主動式ETF",
    "00403A": "統一升級50主動式ETF",
    "00988A": "統一全球創新主動式ETF"
};

function updateEtfLabels(etfCode) {
    const isNavOnly = etfCode !== "00997A";
    
    // Update body class
    if (isNavOnly) {
        document.body.classList.add("is-nav-only");
    } else {
        document.body.classList.remove("is-nav-only");
    }
    
    // Update sidebar footer info badge
    const sidebarBadge = document.querySelector(".sidebar-footer .etf-badge");
    if (sidebarBadge) {
        sidebarBadge.querySelector(".code").textContent = etfCode;
        let shortDesc = "群益美國增長";
        if (etfCode === "00981A") shortDesc = "統一台股增長";
        else if (etfCode === "00403A") shortDesc = "統一升級50";
        else if (etfCode === "00988A") shortDesc = "統一全球創新";
        sidebarBadge.querySelector(".desc").textContent = shortDesc;
    }
    
    // Update header title and subtitle
    const headerTitle = document.getElementById("current-view-title");
    const headerSubtitle = document.querySelector(".top-header .header-title .subtitle");
    
    // Update header subtitle
    if (headerSubtitle) {
        headerSubtitle.textContent = `${etfCode} ${ETF_NAMES[etfCode] || ""} 實時監測系統`;
    }
    
    // Update settings panel label
    const settingsEtfLabel = document.getElementById("settings-etf-label");
    if (settingsEtfLabel) {
        settingsEtfLabel.textContent = etfCode;
    }
    
    // Enable/disable API key input visual state
    const geminiInput = document.getElementById("input-gemini-key");
    if (geminiInput) {
        geminiInput.disabled = false;
        geminiInput.placeholder = "AIxxxxxxxxxxxxxxxxxxxxxxxxxxxx";
    }
}

// Console log function to write output to the settings log area
function logToConsole(message, type = "info") {
    const consoleOutput = document.getElementById("sync-console-output");
    if (!consoleOutput) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    
    if (type === "error") {
        line.className = "err-line";
        line.innerHTML = `[${timestamp}] ❌ <span class="err-text">${message}</span>`;
    } else if (type === "system") {
        line.className = "system-line";
        line.innerHTML = `[${timestamp}] ⚙️ ${message}`;
    } else {
        line.className = "info-line";
        line.innerHTML = `[${timestamp}] 📈 ${message}`;
    }
    
    consoleOutput.appendChild(line);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// Toast notification function
function showToast(message, isError = false) {
    const toast = document.getElementById("toast-notification");
    const toastMessage = document.getElementById("toast-message");
    const toastIcon = document.getElementById("toast-icon");
    
    if (!toast) return;
    
    toastMessage.textContent = message;
    if (isError) {
        toast.className = "toast show error-toast";
        toastIcon.className = "fa-solid fa-circle-exclamation info-icon";
    } else {
        toast.className = "toast show";
        toastIcon.className = "fa-solid fa-circle-check info-icon";
    }
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 4000);
}

// Format numbers
function formatCurrency(val) {
    if (val === null || val === undefined) return "--";
    return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 }).format(val);
}

function formatNumber(val, decimals = 0) {
    if (val === null || val === undefined) return "--";
    return new Intl.NumberFormat('zh-TW', { maximumFractionDigits: decimals }).format(val);
}

// --------------------------------------------------
// DATA LOADING & RENDERING
// --------------------------------------------------

async function loadSummaryData() {
    try {
        const response = await fetch(`/api/summary?etf=${selectedEtf}`);
        const res = await response.json();
        
        if (!res.success) {
            console.error("Summary API Error:", res.error);
            return;
        }
        
        // 1. Update KPI Banners
        document.getElementById("kpi-nav").textContent = res.nav ? res.nav.toFixed(2) : "--.--";
        
        const navChangeEl = document.getElementById("kpi-nav-change");
        const changePct = res.change_percent || "0.00%";
        navChangeEl.textContent = changePct;
        
        // Add styling for up/down change
        navChangeEl.className = "kpi-trend";
        if (changePct.includes("-") || parseFloat(changePct) < 0) {
            navChangeEl.classList.add("down");
        } else if (parseFloat(changePct) > 0) {
            navChangeEl.classList.add("up");
        } else {
            navChangeEl.classList.add("neutral");
        }
        
        // Portfolio Value
        document.getElementById("kpi-portfolio-val").textContent = formatCurrency(res.portfolio_value);
        document.getElementById("kpi-units-val").textContent = formatNumber(res.personal_units);
        
        const portChangeEl = document.getElementById("kpi-portfolio-change");
        const portChangePct = res.portfolio_change_percent;
        const portChangeAmt = res.portfolio_change_amount;
        portChangeEl.textContent = `${portChangeAmt >= 0 ? "+" : ""}${formatNumber(portChangeAmt, 0)} (${portChangePct})`;
        
        portChangeEl.className = "kpi-trend";
        if (portChangeAmt < 0) {
            portChangeEl.classList.add("down");
        } else if (portChangeAmt > 0) {
            portChangeEl.classList.add("up");
        } else {
            portChangeEl.classList.add("neutral");
        }
        
        // Fund Assets & Units
        const assetsBillions = res.fund_assets ? (res.fund_assets / 100000000).toFixed(2) : "--.--";
        document.getElementById("kpi-assets").textContent = `${assetsBillions} 億`;
        document.getElementById("kpi-outstanding-units").textContent = formatNumber(res.outstanding_units);
        
        // Sync Time Header
        document.getElementById("sync-time-val").textContent = res.nav_date || "----/--/--";
        
        // Prefill settings form units
        document.getElementById("input-personal-units").value = res.personal_units || "";
        
    } catch (e) {
        console.error("Error loading summary:", e);
    }
}

async function loadHoldingsData() {
    try {
        const response = await fetch(`/api/holdings?etf=${selectedEtf}`);
        const res = await response.json();
        
        if (!res.success) {
            console.error("Holdings API Error:", res.error);
            return;
        }
        
        const holdings = res.holdings || [];
        const dateVal = res.date || "----/--/--";
        
        document.getElementById("holdings-count-val").textContent = holdings.length;
        document.getElementById("holdings-date-val").textContent = dateVal;
        
        // Calculate total stock weight
        const totalWeight = holdings.reduce((sum, h) => sum + h.weight, 0);
        document.getElementById("holdings-weight-pct").textContent = totalWeight.toFixed(2);
        
        // 1. Renders Top 10 in Dashboard
        const dashboardTopEl = document.getElementById("dashboard-top-holdings");
        if (dashboardTopEl) {
            if (holdings.length === 0) {
                dashboardTopEl.innerHTML = '<div class="no-data"><i class="fa-solid fa-info-circle"></i> 目前無持股資料，請點擊同步更新。</div>';
            } else {
                dashboardTopEl.innerHTML = "";
                // Take top 10 holdings
                holdings.slice(0, 10).forEach((h, index) => {
                    const row = document.createElement("div");
                    row.className = "holding-item-row";
                    row.innerHTML = `
                        <div class="holding-index">${index + 1}</div>
                        <div class="holding-info">
                            <span class="holding-code">${h.code}</span>
                            <span class="holding-name">${h.name}</span>
                        </div>
                        <div class="holding-stats">
                            <span class="holding-weight">${h.weight.toFixed(2)}%</span>
                            <span class="holding-shares">${formatNumber(h.shares)} 股</span>
                        </div>
                    `;
                    dashboardTopEl.appendChild(row);
                });
            }
        }
        
        // 2. Renders Full Table in Holdings Tab
        const tableBody = document.getElementById("holdings-table-body");
        if (tableBody) {
            if (holdings.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" class="no-data-card"><i class="fa-solid fa-info-circle"></i> 暫無持倉數據</td></tr>';
            } else {
                renderHoldingsTable(holdings);
            }
        }
        
        // 3. Renders Changes Details
        const changes = res.changes || { added: [], removed: [], changed: [] };
        const compDateVal = document.getElementById("holdings-compare-date-val");
        if (compDateVal) {
            compDateVal.textContent = res.previous_date ? `相較於 ${res.previous_date}` : "初次持股數據，無前日對比";
        }
        
        // Added list
        const addedList = document.getElementById("holdings-added-list");
        if (addedList) {
            if (changes.added.length === 0) {
                addedList.innerHTML = '<li>無新增持股</li>';
            } else {
                addedList.innerHTML = changes.added.map(h => `
                    <li>
                        <span><strong>${h.code}</strong> <small>${h.name}</small></span>
                        <span class="weight-change text-green">+${h.weight.toFixed(2)}%</span>
                    </li>
                `).join("");
            }
        }
        
        // Removed list
        const removedList = document.getElementById("holdings-removed-list");
        if (removedList) {
            if (changes.removed.length === 0) {
                removedList.innerHTML = '<li>無刪除持股</li>';
            } else {
                removedList.innerHTML = changes.removed.map(h => `
                    <li>
                        <span><strong>${h.code}</strong> <small>${h.name}</small></span>
                        <span class="weight-change text-red">-${h.weight.toFixed(2)}%</span>
                    </li>
                `).join("");
            }
        }
        
        // Changed weights list (Top 10 biggest shifts)
        const changedList = document.getElementById("holdings-changed-list");
        if (changedList) {
            if (changes.changed.length === 0) {
                changedList.innerHTML = '<li>無權重變動</li>';
            } else {
                changedList.innerHTML = changes.changed.slice(0, 10).map(h => {
                    const isUp = h.weight_change > 0;
                    return `
                        <li>
                            <span><strong>${h.code}</strong> <small>${h.name}</small></span>
                            <span class="weight-change ${isUp ? 'text-green' : 'text-red'}">
                                ${isUp ? '+' : ''}${h.weight_change.toFixed(3)}%
                            </span>
                        </li>
                    `;
                }).join("");
            }
        }
        
        // 4. Allocation breakdown
        const allocationEl = document.getElementById("allocation-breakdown");
        if (allocationEl) {
            // Stocks allocation
            const stockPct = totalWeight;
            // Cash and Repo mock calculation based on standard ratios
            const repoPct = 100 - stockPct > 0 ? (100 - stockPct) * 0.4 : 0.0;
            const cashPct = 100 - stockPct - repoPct;
            
            let stockLabel = "美股現貨股票 (Stocks)";
            if (selectedEtf === "00981A" || selectedEtf === "00403A") {
                stockLabel = "台股現貨股票 (Stocks)";
            } else if (selectedEtf === "00988A") {
                stockLabel = "全球現貨股票 (Stocks)";
            }
            
            allocationEl.innerHTML = `
                <div class="allocation-bar-row">
                    <div class="allocation-lbls">
                        <span class="name">${stockLabel}</span>
                        <span class="pct">${stockPct.toFixed(2)}%</span>
                    </div>
                    <div class="allocation-bar-bg">
                        <div class="allocation-bar-fill" style="width: ${stockPct}%"></div>
                    </div>
                </div>
                <div class="allocation-bar-row mt-3">
                    <div class="allocation-lbls">
                        <span class="name">債券附買回 (Repos)</span>
                        <span class="pct">${repoPct.toFixed(2)}%</span>
                    </div>
                    <div class="allocation-bar-bg">
                        <div class="allocation-bar-fill" style="width: ${repoPct}%; background: var(--secondary);"></div>
                    </div>
                </div>
                <div class="allocation-bar-row mt-3">
                    <div class="allocation-lbls">
                        <span class="name">美元與台幣現金 (Cash)</span>
                        <span class="pct">${cashPct.toFixed(2)}%</span>
                    </div>
                    <div class="allocation-bar-bg">
                        <div class="allocation-bar-fill" style="width: ${cashPct}%; background: var(--text-muted);"></div>
                    </div>
                </div>
            `;
        }
        
        // Global search filtering on holdings table
        const searchInput = document.getElementById("holdings-search-input");
        if (searchInput) {
            // Remove previous event listeners by cloning
            const newSearchInput = searchInput.cloneNode(true);
            searchInput.parentNode.replaceChild(newSearchInput, searchInput);
            
            newSearchInput.addEventListener("input", (e) => {
                const query = e.target.value.toLowerCase().trim();
                const filtered = holdings.filter(h => 
                    h.code.toLowerCase().includes(query) || 
                    h.name.toLowerCase().includes(query)
                );
                renderHoldingsTable(filtered);
            });
        }
        
    } catch (e) {
        console.error("Error loading holdings:", e);
    }
}

function renderHoldingsTable(holdingsList) {
    const tableBody = document.getElementById("holdings-table-body");
    if (!tableBody) return;
    
    tableBody.innerHTML = "";
    holdingsList.forEach((h, index) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${index + 1}</td>
            <td class="font-bold">${h.code}</td>
            <td class="text-secondary">${h.name}</td>
            <td class="text-right font-semibold text-purple">${h.weight.toFixed(4)}%</td>
            <td class="text-right text-secondary">${formatNumber(h.shares)}</td>
        `;
        tableBody.appendChild(row);
    });
}

async function loadHistoryDataAndDrawCharts() {
    try {
        const response = await fetch(`/api/history?etf=${selectedEtf}`);
        const res = await response.json();
        
        if (!res.success) {
            console.error("History API Error:", res.error);
            return;
        }
        
        const history = res.history || [];
        
        // 1. Draw Dashboard Chart (Portfolio Value)
        drawDashboardChart(history.slice(-7));
        
        // 2. Draw History Tab Chart (Double axis NAV vs Portfolio Value)
        drawHistoryTabChart(history);
        
        // 3. Render Table in History Tab
        const tableBody = document.getElementById("history-table-body");
        if (tableBody) {
            tableBody.innerHTML = "";
            if (history.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="6" class="no-data-card">無歷史資料</td></tr>';
            } else {
                // Render from latest to oldest in table
                [...history].reverse().forEach(h => {
                    const row = document.createElement("tr");
                    const changeVal = h.nav ? h.change_percent || "0.0%" : "0.0%";
                    const isDown = changeVal.includes("-");
                    const changeClass = isDown ? "text-red" : (changeVal !== "0.0%" && changeVal !== "0" && changeVal !== "0.00" && !changeVal.startsWith("0") ? "text-green" : "");
                    
                    row.innerHTML = `
                        <td class="font-bold">${h.date}</td>
                        <td class="text-right">${h.nav ? h.nav.toFixed(2) : "--.--"}</td>
                        <td class="text-right ${changeClass}">${changeVal}</td>
                        <td class="text-right text-secondary">${h.fund_assets ? formatCurrency(h.fund_assets) : "--"}</td>
                        <td class="text-right text-secondary">${h.outstanding_units ? formatNumber(h.outstanding_units) : "--"}</td>
                        <td class="text-right font-bold text-purple">${h.portfolio_value ? formatCurrency(h.portfolio_value) : "$0"}</td>
                    `;
                    tableBody.appendChild(row);
                });
            }
        }
    } catch (e) {
        console.error("Error loading history:", e);
    }
}

function drawDashboardChart(history) {
    const ctx = document.getElementById("dashboardChart");
    if (!ctx) return;
    
    // Destroy existing instance to avoid duplicate renders
    if (dashboardChartInstance) {
        dashboardChartInstance.destroy();
    }
    
    // Use history list directly
    const labels = history.map(h => h.date.substring(5)); // just MM-DD
    
    let label = '持倉估值 (TWD)';
    let values = history.map(h => h.portfolio_value);
    let borderColor = '#7c4dff';
    let backgroundColor = 'rgba(124, 77, 255, 0.1)';
    let pointColor = '#00bcd4';
    
    if (currentChartType === "nav") {
        label = '基金淨值 (TWD)';
        values = history.map(h => h.nav);
        borderColor = '#00bcd4';
        backgroundColor = 'rgba(0, 188, 212, 0.1)';
        pointColor = '#7c4dff';
    }
    
    dashboardChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: values,
                borderColor: borderColor,
                backgroundColor: backgroundColor,
                borderWidth: 3,
                tension: 0.35,
                fill: true,
                pointBackgroundColor: pointColor,
                pointHoverRadius: 7,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8892b0' }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8892b0' }
                }
            }
        }
    });
}

function drawHistoryTabChart(history) {
    const ctx = document.getElementById("historyChart");
    if (!ctx) return;
    
    if (historyChartInstance) {
        historyChartInstance.destroy();
    }
    
    const labels = history.map(h => h.date);
    const navs = history.map(h => h.nav);
    const portValues = history.map(h => h.portfolio_value);
    
    historyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '基金淨值 (NAV)',
                    data: navs,
                    borderColor: '#00bcd4', // Cyan
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: 'y-nav',
                    fill: false
                },
                {
                    label: '個人持倉總額 (TWD)',
                    data: portValues,
                    borderColor: '#7c4dff', // Purple
                    backgroundColor: 'rgba(124, 77, 255, 0.05)',
                    borderWidth: 3,
                    tension: 0.35,
                    yAxisID: 'y-port',
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8892b0' }
                },
                'y-nav': {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#00bcd4' },
                    title: { display: true, text: 'NAV (TWD)', color: '#00bcd4' }
                },
                'y-port': {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#7c4dff' },
                    title: { display: true, text: '持倉估值 (TWD)', color: '#7c4dff' }
                }
            }
        }
    });
}

async function loadAnnouncements() {
    try {
        if (selectedEtf !== "00997A") {
            const dashNewsEl = document.getElementById("dashboard-latest-news");
            if (dashNewsEl) {
                dashNewsEl.innerHTML = '<div class="no-data"><i class="fa-solid fa-circle-info"></i> 重要公告目前僅支援群益投信 ETF</div>';
            }
            return;
        }
        const response = await fetch(`/api/announcements?etf=${selectedEtf}`);
        const res = await response.json();
        
        if (!res.success) {
            console.error("Announcements API Error:", res.error);
            return;
        }
        
        const list = res.announcements || [];
        
        // 1. Dashboard summary (Top 4)
        const dashNewsEl = document.getElementById("dashboard-latest-news");
        if (dashNewsEl) {
            if (list.length === 0) {
                dashNewsEl.innerHTML = '<div class="no-data"><i class="fa-solid fa-circle-info"></i> 目前暫無公告消息</div>';
            } else {
                dashNewsEl.innerHTML = "";
                list.slice(0, 4).forEach(item => {
                    const row = document.createElement("a");
                    row.href = item.url;
                    row.target = "_blank";
                    row.className = "news-item-row";
                    row.innerHTML = `
                        <div class="news-row-meta">
                            <span class="news-tag">00997A 公告</span>
                            <span class="news-date">${item.date}</span>
                        </div>
                        <div class="news-row-title">${item.title}</div>
                    `;
                    dashNewsEl.appendChild(row);
                });
            }
        }
        
        // 2. Announcements Tab feed list
        const feedEl = document.getElementById("announcements-feed-list");
        if (feedEl) {
            if (list.length === 0) {
                feedEl.innerHTML = '<div class="no-data-card"><i class="fa-solid fa-bullhorn"></i> 尚未同步到相關公告</div>';
            } else {
                feedEl.innerHTML = "";
                list.forEach(item => {
                    const card = document.createElement("a");
                    card.href = item.url;
                    card.target = "_blank";
                    card.className = "announcement-card-item";
                    card.innerHTML = `
                        <div class="announcement-meta">
                            <span class="announcement-label">群益投信公告</span>
                            <span class="announcement-date">${item.date}</span>
                        </div>
                        <div class="announcement-title">${item.title}</div>
                    `;
                    feedEl.appendChild(card);
                });
            }
        }
    } catch (e) {
        console.error("Error loading announcements:", e);
    }
}

async function loadAiAnalysisReport(range = null, force = false) {
    if (range === null) {
        range = getActiveAiRange();
    }
    
    const summaryEl = document.getElementById("dashboard-ai-summary");
    const refreshBtn = document.getElementById("btn-trigger-ai-refresh");
    const exportBtn = document.getElementById("btn-export-ai-html");
    
    if (summaryEl) {
        if (force) {
            summaryEl.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-spinner fa-spin"></i> AI 正在分析 ${range}日成分股異動與核心持股，這可能需要數秒時間...</div>`;
        }
    }
    
    if (refreshBtn && force) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 分析中...';
    }
    
    try {
        const url = `/api/ai-analysis?etf=${selectedEtf}&range=${range}${force ? '&force=1' : ''}`;
        const response = await fetch(url);
        const res = await response.json();
        
        if (summaryEl) {
            if (res.success) {
                if (res.report) {
                    // Parse markdown output using marked.js
                    summaryEl.innerHTML = marked.parse(res.report);
                    if (exportBtn) exportBtn.style.display = "inline-flex";
                } else {
                    summaryEl.innerHTML = `
                        <div class="no-data-placeholder" style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
                            <i class="fa-solid fa-brain" style="font-size: 3rem; color: var(--primary); margin-bottom: 16px; display: block; opacity: 0.6;"></i>
                            <p style="font-weight: 500; font-size: 1.1rem; margin-bottom: 8px;">尚未生成此時間區間的 AI 分析報告</p>
                            <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 20px;">請點擊右上方「AI分析」按鈕，即可開始對成分股變動與前十大持股進行深入診斷。</p>
                        </div>
                    `;
                    if (exportBtn) exportBtn.style.display = "none";
                }
            } else {
                summaryEl.innerHTML = `<p class="text-muted">載入 AI ${range}日操盤建議失敗，或尚未完成成分股同步運算。</p>`;
                if (exportBtn) exportBtn.style.display = "none";
            }
        }
    } catch (e) {
        console.error("Error loading AI report:", e);
        if (summaryEl) {
            summaryEl.innerHTML = `<p class="text-muted">連線至 AI 分析模組時發生錯誤: ${e.message}</p>`;
        }
        if (exportBtn) exportBtn.style.display = "none";
    } finally {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> AI分析';
        }
    }
}

function getActiveAiRange() {
    const activeBtn = document.querySelector(".ai-range-btn.active");
    return activeBtn ? parseInt(activeBtn.getAttribute("data-range")) : 1;
}

function exportAiReportToHtml() {
    const summaryEl = document.getElementById("dashboard-ai-summary");
    if (!summaryEl) return;
    
    // Check if report has placeholder text
    if (summaryEl.querySelector(".no-data-placeholder")) {
        showToast("無分析報告可供匯出，請先點擊「AI分析」按鈕。", true);
        return;
    }
    
    const reportContent = summaryEl.innerHTML;
    const activeRange = getActiveAiRange();
    const latestDate = document.getElementById("sync-time-val").textContent || new Date().toLocaleDateString();
    
    const etfName = ETF_NAMES[selectedEtf] || "主動式 ETF";
    
    const htmlContent = `
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${selectedEtf} AI ${activeRange}日操盤分析與行動建議報告 (${latestDate})</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', 'Noto Sans TC', sans-serif;
            background-color: #0b0c16;
            color: #e2e8f0;
            line-height: 1.7;
            padding: 40px 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif;
            color: #ffffff;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }
        h1 {
            font-size: 2rem;
            border-bottom: 2px solid #7c4dff;
            padding-bottom: 10px;
            margin-top: 0;
        }
        h2 {
            font-size: 1.5rem;
            color: #00bcd4;
        }
        h3 {
            font-size: 1.2rem;
        }
        p {
            margin-bottom: 1.2em;
        }
        ul, ol {
            margin-bottom: 1.2em;
            padding-left: 20px;
        }
        li {
            margin-bottom: 0.5em;
        }
        strong {
            color: #7c4dff;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: rgba(124, 77, 255, 0.1);
            color: #ffffff;
        }
        tr:nth-child(even) td {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .footer {
            margin-top: 50px;
            font-size: 0.85rem;
            color: #8892b0;
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <h1>${selectedEtf} ${etfName}</h1>
    <h2>AI ${activeRange}日操盤分析與行動建議報告</h2>
    <p><strong>報告日期</strong>: ${latestDate} &nbsp;|&nbsp; <strong>評估區間</strong>: 過去 ${activeRange} 個交易日</p>
    <hr style="border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 20px 0;">
    <div>
        ${reportContent}
    </div>
    <div class="footer">
        此報告由 ${selectedEtf} ETF Tracker AI 分析模組自動產出。投資有風險，本文僅供參考，不構成投資建議。
    </div>
</body>
</html>
    `;
    
    const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedEtf}_AI_Report_${activeRange}D_${latestDate}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast("報告已成功匯出為 HTML 檔案！");
}

// --------------------------------------------------
// ACTIONS AND CONTROL LOGIC
// --------------------------------------------------

// Handles manual background synchronization
async function triggerSyncTask(forceAi = false) {
    const btnSync = document.getElementById("btn-manual-sync");
    const btnHeaderSync = document.getElementById("btn-header-sync");
    const btnForceAi = document.getElementById("btn-force-ai-run");
    
    // Disable buttons during sync
    btnSync.disabled = true;
    btnHeaderSync.disabled = true;
    btnForceAi.disabled = true;
    
    btnSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 同步資料中...';
    btnHeaderSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    
    logToConsole("手動同步已觸發。正在呼叫後台 Scraper 任務...", "system");
    
    try {
        const response = await fetch("/api/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ force_ai: forceAi })
        });
        const res = await response.json();
        
        if (res.success) {
            logToConsole("同步資料庫成功！最新基金淨值、PCF持倉及重要公告均已儲存。", "info");
            showToast("數據同步完成！");
            
            // Reload all dashboard panels
            await loadSummaryData();
            await loadHoldingsData();
            await loadHistoryDataAndDrawCharts();
            await loadAnnouncements();
            await loadAiAnalysisReport();
        } else {
            logToConsole(`同步失敗: ${res.error}`, "error");
            showToast(`同步失敗: ${res.error}`, true);
        }
    } catch (e) {
        logToConsole(`網路連線異常，無法完成同步: ${e.message}`, "error");
        showToast("同步連線失敗", true);
    } finally {
        btnSync.disabled = false;
        btnHeaderSync.disabled = false;
        btnForceAi.disabled = false;
        btnSync.innerHTML = '<i class="fa-solid fa-rotate"></i> 手動同步最新數據';
        btnHeaderSync.innerHTML = '<i class="fa-solid fa-sync"></i> 立即同步';
    }
}

// --------------------------------------------------
// APP ROUTING AND CONTROLLERS SETUP
// --------------------------------------------------

function setupTabNavigation() {
    const navItems = document.querySelectorAll(".nav-menu .nav-item");
    const titleEl = document.getElementById("current-view-title");
    
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            
            // Toggle active navigation
            navItems.forEach(n => n.classList.remove("active"));
            item.classList.add("active");
            
            // Show corresponding tab body
            const tabId = item.getAttribute("data-tab");
            document.querySelectorAll(".content-body .tab-pane").forEach(pane => {
                pane.classList.remove("active");
            });
            document.getElementById(`${tabId}-tab`).classList.add("active");
            
            // Update Top Header title text
            titleEl.textContent = item.querySelector("span").textContent;
            
            // Custom redraw logic for Chart.js instances (required when container was hidden)
            if (tabId === "history" && historyChartInstance) {
                setTimeout(() => historyChartInstance.resize(), 100);
            }
            if (tabId === "dashboard" && dashboardChartInstance) {
                setTimeout(() => dashboardChartInstance.resize(), 100);
            }
        });
    });
    
    // Quick links routing
    const linkHoldings = document.getElementById("link-view-all-holdings");
    if (linkHoldings) {
        linkHoldings.addEventListener("click", (e) => {
            e.preventDefault();
            document.querySelector('.nav-item[data-tab="holdings"]').click();
        });
    }
    
    const linkNews = document.getElementById("link-view-all-news");
    if (linkNews) {
        linkNews.addEventListener("click", (e) => {
            e.preventDefault();
            document.querySelector('.nav-item[data-tab="announcements"]').click();
        });
    }
}

function setupSettingsController() {
    const btnSave = document.getElementById("btn-save-settings");
    
    btnSave.addEventListener("click", async () => {
        const unitsVal = document.getElementById("input-personal-units").value;
        const geminiKey = document.getElementById("input-gemini-key").value;
        
        const payload = {
            etf: selectedEtf
        };
        if (unitsVal !== "") {
            payload.personal_units = parseFloat(unitsVal);
        }
        if (geminiKey !== "" && !geminiKey.includes("••••")) {
            payload.gemini_key = geminiKey;
        }
        
        btnSave.disabled = true;
        btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 儲存中...';
        
        try {
            const response = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const res = await response.json();
            
            if (res.success) {
                showToast("設定已成功儲存！");
                logToConsole("個人設定更新成功。", "system");
                // Reload summary values to recalculate portfolio totals
                await loadSummaryData();
                await loadHistoryDataAndDrawCharts();
            } else {
                showToast(res.error, true);
            }
        } catch (e) {
            showToast("伺服器通訊錯誤", true);
        } finally {
            btnSave.disabled = false;
            btnSave.innerHTML = '<i class="fa-solid fa-save"></i> 儲存設定';
        }
    });
    
    // Password visibility toggle for API Key
    const passInput = document.getElementById("input-gemini-key");
    const toggleBtn = document.getElementById("btn-toggle-key-visibility");
    
    toggleBtn.addEventListener("click", () => {
        const isPassword = passInput.type === "password";
        passInput.type = isPassword ? "text" : "password";
        toggleBtn.querySelector("i").className = isPassword ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
    });
    
    // Console log cleaning
    document.getElementById("btn-clear-logs").addEventListener("click", () => {
        document.getElementById("sync-console-output").innerHTML = '<div class="system-line">[System] 日誌主控台已清空。</div>';
    });
}

function setupTriggerButtons() {
    // Top header sync button
    document.getElementById("btn-header-sync").addEventListener("click", () => {
        triggerSyncTask();
    });
    
    // Settings manual sync button
    document.getElementById("btn-manual-sync").addEventListener("click", () => {
        triggerSyncTask(false);
    });
    
    // Force AI Analysis refresh button
    document.getElementById("btn-force-ai-run").addEventListener("click", () => {
        triggerSyncTask(true);
    });
    
    // AI Refresh shortcut button in dashboard card
    document.getElementById("btn-trigger-ai-refresh").addEventListener("click", async () => {
        const range = getActiveAiRange();
        await loadAiAnalysisReport(range, true);
    });
    
    // Home Dashboard AI range filters toggle (1D, 5D, 10D)
    document.querySelectorAll(".ai-range-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            if (btn.classList.contains("active")) return;
            
            document.querySelectorAll(".ai-range-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const range = parseInt(btn.getAttribute("data-range"));
            await loadAiAnalysisReport(range);
        });
    });
    
    // Home Dashboard chart filters toggle (7D, 30D, ALL)
    document.querySelectorAll(".chart-time-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            document.querySelectorAll(".chart-time-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const days = parseInt(btn.getAttribute("data-days"));
            try {
                const response = await fetch(`/api/history?etf=${selectedEtf}&limit=${days}`);
                const res = await response.json();
                if (res.success && res.history) {
                    drawDashboardChart(res.history);
                }
            } catch (e) {
                console.error("Error toggling chart range:", e);
            }
        });
    });

    // Chart Type Segment Tabs selector (Portfolio Value vs NAV Trend)
    document.querySelectorAll(".chart-tab").forEach(tab => {
        tab.addEventListener("click", async (e) => {
            if (tab.classList.contains("active")) return;
            
            document.querySelectorAll(".chart-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            currentChartType = tab.getAttribute("data-type");
            
            // Refresh chart based on currently selected active range days
            const activeBtn = document.querySelector(".chart-time-btn.active");
            const days = activeBtn ? parseInt(activeBtn.getAttribute("data-days")) : 7;
            
            try {
                const response = await fetch(`/api/history?etf=${selectedEtf}&limit=${days}`);
                const res = await response.json();
                if (res.success && res.history) {
                    drawDashboardChart(res.history);
                }
            } catch (e) {
                console.error("Error toggling chart type:", e);
            }
        });
    });

    // Holdings sub-tabs toggle navigation
    document.querySelectorAll(".sub-tab-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            if (btn.classList.contains("active")) return;
            
            document.querySelectorAll(".sub-tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const targetPaneId = btn.getAttribute("data-subtab") + "-pane";
            document.querySelectorAll(".sub-tab-pane").forEach(pane => {
                pane.classList.remove("active");
            });
            document.getElementById(targetPaneId).classList.add("active");
        });
    });

    // Export AI Report to HTML file
    const exportBtn = document.getElementById("btn-export-ai-html");
    if (exportBtn) {
        exportBtn.addEventListener("click", () => {
            exportAiReportToHtml();
        });
    }
}

// --------------------------------------------------
// APP INIT
// --------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
    // Setup controls & interactions
    setupTabNavigation();
    setupSettingsController();
    setupTriggerButtons();
    
    // Setup ETF selector dropdown listener
    const selector = document.getElementById("etf-selector");
    if (selector) {
        selector.addEventListener("change", async (e) => {
            selectedEtf = e.target.value;
            updateEtfLabels(selectedEtf);
            
            // Reload all views
            await loadSummaryData();
            await loadHoldingsData();
            await loadHistoryDataAndDrawCharts();
            await loadAnnouncements();
            await loadAiAnalysisReport();
        });
    }
    
    // Fetch and populate settings inputs (Gemini Key preview check)
    // Prefill masking for Gemini Key if it exists in local environment
    try {
        const response = await fetch(`/api/ai-analysis?etf=${selectedEtf}`);
        const res = await response.json();
        if (res.success && res.report && !res.report.includes("尚未設定 Gemini API Key")) {
            // Seemingly key exists, mask the display
            document.getElementById("input-gemini-key").placeholder = "••••••••••••••••••••••••••••••••";
        }
    } catch(e) {}

    // Load initial views
    updateEtfLabels(selectedEtf);
    await loadSummaryData();
    await loadHoldingsData();
    await loadHistoryDataAndDrawCharts();
    await loadAnnouncements();
    await loadAiAnalysisReport();
});
