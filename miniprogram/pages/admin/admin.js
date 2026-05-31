const api = require('../../utils/api');

const STATUS_TEXT = {
  submitted: '待受理', assigned: '已分配', in_progress: '维修中', done: '已完成', closed: '已关闭',
};

function fmtDate(d) {
  const p = (n) => (n < 10 ? '0' + n : '' + n);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

Page({
  data: {
    tab: 'booking',
    tabs: [
      { k: 'booking', label: '预约审批' },
      { k: 'repair', label: '报修流转' },
      { k: 'schedule', label: '课表导入' },
      { k: 'faq', label: '知识库' },
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
  },

  onShow() {
    const u = getApp().globalData.userInfo;
    if (!u || u.role !== 'admin') {
      wx.showToast({ title: '需要管理员权限', icon: 'none' });
      wx.navigateBack();
      return;
    }
    this.loadTab();
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.k }, () => this.loadTab());
  },

  loadTab() {
    if (this.data.tab === 'booking') this.loadBookings();
    else if (this.data.tab === 'repair') this.loadRepairs();
    else if (this.data.tab === 'faq') this.loadFaqs();
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
});
