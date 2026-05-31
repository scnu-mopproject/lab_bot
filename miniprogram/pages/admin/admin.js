const api = require('../../utils/api');

const STATUS_TEXT = {
  submitted: '待受理', assigned: '已分配', in_progress: '维修中', done: '已完成', closed: '已关闭',
};

function fmtDate(d) {
  const p = (n) => (n < 10 ? '0' + n : '' + n);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const REPAIR_ALL = ['submitted', 'assigned', 'in_progress', 'done', 'closed'];

Page({
  data: {
    tab: 'dashboard',
    tabs: [
      { k: 'dashboard', label: '看板' },
      { k: 'booking', label: '审批' },
      { k: 'repair', label: '报修' },
      { k: 'schedule', label: '课表' },
      { k: 'faq', label: '知识库' },
      { k: 'report', label: '报表' },
    ],
    bookings: [],
    repairs: [],
    faqs: [],
    faqForm: { question: '', answer: '', keywords: '' },
    termStart: fmtDate(new Date()),
    filePath: '',
    fileName: '',
    importResult: null,
    statusText: STATUS_TEXT,
    // 看板
    dashboard: null,
    repairBars: [],
    // 报表
    report: { type: 'bookings', start: '', end: '' },
    reportTypes: [
      { k: 'bookings', label: '预约报表' },
      { k: 'repairs', label: '报修报表' },
    ],
  },

  onShow() {
    const u = getApp().globalData.userInfo;
    if (!u || u.role !== 'admin') {
      wx.showToast({ title: '需要管理员权限', icon: 'none' });
      wx.navigateBack();
      return;
    }
    if (!this.data.report.start) {
      const now = new Date();
      const ago = new Date(now.getTime() - 30 * 86400000);
      this.setData({ 'report.start': fmtDate(ago), 'report.end': fmtDate(now) });
    }
    this.loadTab();
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.k }, () => this.loadTab());
  },

  loadTab() {
    if (this.data.tab === 'dashboard') this.loadDashboard();
    else if (this.data.tab === 'booking') this.loadBookings();
    else if (this.data.tab === 'repair') this.loadRepairs();
    else if (this.data.tab === 'faq') this.loadFaqs();
  },

  async loadDashboard() {
    try {
      const d = await api.get('/api/admin/dashboard');
      // 报修状态分布转成可渲染的条形数据
      const total = REPAIR_ALL.reduce((s, k) => s + (d.repair_status[k] || 0), 0) || 1;
      const repairBars = REPAIR_ALL.map((k) => ({
        key: k, label: STATUS_TEXT[k], count: d.repair_status[k] || 0,
        pct: Math.round(((d.repair_status[k] || 0) / total) * 100),
      }));
      // 高频问题按最大值归一化用于画条
      const maxQ = Math.max(1, ...d.hot_questions.map((q) => q.count));
      d.hot_questions = d.hot_questions.map((q) => ({ ...q, pct: Math.round((q.count / maxQ) * 100) }));
      const maxU = Math.max(1, ...d.room_usage.map((q) => q.count));
      d.room_usage = d.room_usage.map((q) => ({ ...q, pct: Math.round((q.count / maxU) * 100) }));
      this.setData({ dashboard: d, repairBars });
    } catch (e) {}
  },

  async loadBookings() {
    try { this.setData({ bookings: await api.get('/api/admin/bookings', { status: 'pending' }) }); } catch (e) {}
  },
  async loadRepairs() {
    try { this.setData({ repairs: await api.get('/api/admin/repairs') }); } catch (e) {}
  },
  async loadFaqs() {
    try { this.setData({ faqs: await api.get('/api/admin/faqs') }); } catch (e) {}
  },

  async review(e) {
    const { id, ok } = e.currentTarget.dataset;
    try {
      await api.post(`/api/admin/bookings/${id}/review`, { approve: ok === 'true' || ok === true });
      wx.showToast({ title: '已处理', icon: 'success' });
      this.loadBookings();
    } catch (e) {}
  },

  goRepair(e) {
    wx.navigateTo({ url: '/pages/repair-detail/repair-detail?id=' + e.currentTarget.dataset.id });
  },

  // 课表导入
  onTermStart(e) { this.setData({ termStart: e.detail.value }); },
  chooseFile() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['csv', 'xlsx'],
      success: (res) => {
        const f = res.tempFiles[0];
        this.setData({ filePath: f.path, fileName: f.name });
      },
    });
  },
  doImport() {
    const app = getApp();
    wx.showLoading({ title: '导入中' });
    wx.uploadFile({
      url: app.globalData.baseUrl + '/api/admin/schedules/import',
      filePath: this.data.filePath,
      name: 'file',
      formData: { term_start_monday: this.data.termStart },
      header: { Authorization: 'Bearer ' + app.globalData.token },
      success: (res) => {
        wx.hideLoading();
        try {
          const data = JSON.parse(res.data);
          if (res.statusCode === 200) {
            this.setData({ importResult: data });
            wx.showToast({ title: '导入完成', icon: 'success' });
          } else {
            wx.showToast({ title: data.detail || '导入失败', icon: 'none' });
          }
        } catch (e) { wx.showToast({ title: '响应解析失败', icon: 'none' }); }
      },
      fail: () => { wx.hideLoading(); wx.showToast({ title: '上传失败', icon: 'none' }); },
    });
  },

  // FAQ
  onFaq(e) { this.setData({ ['faqForm.' + e.currentTarget.dataset.k]: e.detail.value }); },
  async addFaq() {
    const f = this.data.faqForm;
    if (!f.question || !f.answer) { wx.showToast({ title: '请填写问答', icon: 'none' }); return; }
    try {
      await api.post('/api/admin/faqs', f);
      wx.showToast({ title: '已保存', icon: 'success' });
      this.setData({ faqForm: { question: '', answer: '', keywords: '' } });
      this.loadFaqs();
    } catch (e) {}
  },
  async delFaq(e) {
    try { await api.del('/api/admin/faqs/' + e.currentTarget.dataset.id); this.loadFaqs(); } catch (e) {}
  },

  // ---------- 报表导出 ----------
  pickReportType(e) { this.setData({ 'report.type': e.currentTarget.dataset.k }); },
  onReportStart(e) { this.setData({ 'report.start': e.detail.value }); },
  onReportEnd(e) { this.setData({ 'report.end': e.detail.value }); },

  exportReport() {
    const app = getApp();
    const { type, start, end } = this.data.report;
    if (start && end && start > end) {
      wx.showToast({ title: '起始日期不能晚于结束', icon: 'none' });
      return;
    }
    const q = [];
    if (start) q.push('start=' + start);
    if (end) q.push('end=' + end);
    const url = `${app.globalData.baseUrl}/api/admin/reports/${type}.xlsx${q.length ? '?' + q.join('&') : ''}`;
    wx.showLoading({ title: '生成中' });
    wx.downloadFile({
      url,
      header: { Authorization: 'Bearer ' + app.globalData.token },
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode !== 200) { wx.showToast({ title: '导出失败', icon: 'none' }); return; }
        // 打开 Excel（可在微信内预览/转发保存）
        wx.openDocument({
          filePath: res.tempFilePath,
          fileType: 'xlsx',
          showMenu: true,
          fail: () => wx.showToast({ title: '已下载，无法预览', icon: 'none' }),
        });
      },
      fail: () => { wx.hideLoading(); wx.showToast({ title: '下载失败', icon: 'none' }); },
    });
  },
});
