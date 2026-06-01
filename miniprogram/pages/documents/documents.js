const api = require('../../utils/api');

Page({
  data: {
    keyword: '',
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: true,
    loading: false,
  },

  onShow() {
    if (!getApp().globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.load(true);
  },

  onKeyword(e) { this.setData({ keyword: e.detail.value }); },
  doSearch() { this.load(true); },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) this.load(false);
  },

  load(reset) {
    if (this.data.loading) return;
    const page = reset ? 1 : this.data.page;
    this.setData({ loading: true });
    api.get('/api/admin/documents', { page, page_size: this.data.pageSize, keyword: this.data.keyword })
      .then((res) => {
        const items = reset ? res.items : this.data.items.concat(res.items);
        this.setData({
          items,
          total: res.total,
          page: page + 1,
          hasMore: items.length < res.total,
          loading: false,
        });
      })
      .catch(() => this.setData({ loading: false }));
  },

  upload() {
    const app = getApp();
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['txt', 'md', 'pdf', 'docx', 'xlsx', 'zip'],
      success: (res) => {
        const f = res.tempFiles[0];
        const isZip = /\.zip$/i.test(f.name);
        const url = app.globalData.baseUrl + (isZip ? '/api/admin/documents/batch' : '/api/admin/documents');
        wx.showLoading({ title: isZip ? '解压建索引中' : '解析建索引中', mask: true });
        wx.uploadFile({
          url,
          filePath: f.path,
          name: 'file',
          formData: isZip ? {} : { title: f.name },
          header: { Authorization: 'Bearer ' + app.globalData.token },
          success: (r) => {
            wx.hideLoading();
            let data = {};
            try { data = JSON.parse(r.data); } catch (e) {}
            if (r.statusCode === 200) {
              if (isZip) {
                wx.showModal({
                  title: '导入完成',
                  content: `新增 ${data.created} 个，去重跳过 ${data.duplicated} 个` +
                    (data.skipped && data.skipped.length ? `，未处理 ${data.skipped.length} 个` : ''),
                  showCancel: false,
                });
              } else {
                wx.showToast({ title: '已上传', icon: 'success' });
              }
              this.load(true);
            } else {
              wx.showToast({ title: data.detail || '上传失败', icon: 'none' });
            }
          },
          fail: () => { wx.hideLoading(); wx.showToast({ title: '上传失败', icon: 'none' }); },
        });
      },
    });
  },

  async reindex() {
    const ok = await new Promise((r) => wx.showModal({
      title: '重建索引',
      content: '将用当前向量化方案重新计算所有文档向量，文档较多时稍慢，确定继续？',
      success: (m) => r(m.confirm),
    }));
    if (!ok) return;
    wx.showLoading({ title: '重建中', mask: true });
    try {
      const res = await api.post('/api/admin/documents/reindex');
      wx.hideLoading();
      wx.showModal({
        title: '完成',
        content: `已重建 ${res.documents} 个文档、${res.chunks} 个片段（向量化:${res.embedding_model}）`,
        showCancel: false,
      });
    } catch (e) { wx.hideLoading(); }
  },

  async delDoc(e) {
    const ok = await new Promise((r) => wx.showModal({ title: '删除该文档？', success: (m) => r(m.confirm) }));
    if (!ok) return;
    try {
      await api.del('/api/admin/documents/' + e.currentTarget.dataset.id);
      wx.showToast({ title: '已删除', icon: 'success' });
      this.load(true);
    } catch (e) {}
  },
});
