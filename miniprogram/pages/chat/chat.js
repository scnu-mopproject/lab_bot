const api = require('../../utils/api');

Page({
  data: {
    messages: [],
    draft: '',
    loading: false,
    anchor: '',
    quick: ['如何预约实验室？', '设备坏了怎么报修？', '报修进度在哪看？', '实验室开放时间？'],
  },

  onShow() {
    if (!getApp().globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); }
  },

  onInput(e) { this.setData({ draft: e.detail.value }); },

  askQuick(e) {
    this.setData({ draft: e.currentTarget.dataset.q }, () => this.send());
  },

  async send() {
    const text = this.data.draft.trim();
    if (!text || this.data.loading) return;

    const messages = this.data.messages.concat({ role: 'user', content: text });
    this.setData({ messages, draft: '', loading: true });
    this.scrollToEnd();

    // 取最近若干轮作为上下文
    const history = this.data.messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const res = await api.post('/api/chat', { message: text, history });
      const next = this.data.messages.concat({
        role: 'assistant', content: res.reply, sources: res.sources,
      });
      this.setData({ messages: next });
    } catch (e) {
      const next = this.data.messages.concat({ role: 'assistant', content: '抱歉，暂时无法回答，请稍后再试。' });
      this.setData({ messages: next });
    } finally {
      this.setData({ loading: false });
      this.scrollToEnd();
    }
  },

  scrollToEnd() {
    this.setData({ anchor: 'm' + this.data.messages.length });
  },
});
