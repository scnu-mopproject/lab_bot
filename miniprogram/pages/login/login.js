const api = require('../../utils/api');

Page({
  data: {
    showDev: false,
    ssoId: '',
    name: '',
    role: 'student',
  },

  toggleDev() {
    this.setData({ showDev: !this.data.showDev });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.k]: e.detail.value });
  },

  onRole(e) {
    this.setData({ role: e.currentTarget.dataset.r });
  },

  // 校园统一认证：请求登录地址，用 web-view 打开，回调后由后端带回 token
  async onSSOLogin() {
    try {
      const { url } = await api.get('/api/auth/sso/login-url');
      // 实际项目：用 web-view 页面打开 url，监听回调页携带的 token
      wx.showModal({
        title: '统一认证',
        content: '将打开学校统一认证页面：\n' + url + '\n\n（mock 模式下请用下方调试入口）',
        showCancel: false,
      });
    } catch (e) {
      // 错误已在 api 层提示
    }
  },

  async onDevLogin() {
    if (!this.data.ssoId) {
      wx.showToast({ title: '请输入学号/工号', icon: 'none' });
      return;
    }
    try {
      const res = await api.post('/api/auth/dev-login', {
        sso_id: this.data.ssoId,
        name: this.data.name || '测试用户',
        role: this.data.role,
      });
      getApp().setLogin(res.access_token, res.user);
      wx.switchTab({ url: '/pages/booking/booking' });
    } catch (e) {}
  },
});
