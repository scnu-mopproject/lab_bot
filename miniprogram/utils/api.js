// 统一请求封装：自动带 token、统一错误处理
const app = getApp();

function request(method, path, data) {
  const a = getApp();
  return new Promise((resolve, reject) => {
    wx.request({
      url: a.globalData.baseUrl + path,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        Authorization: a.globalData.token ? 'Bearer ' + a.globalData.token : '',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          wx.showToast({ title: '登录已失效', icon: 'none' });
          a.logout();
          reject(res.data);
        } else {
          const msg = (res.data && res.data.detail) || '请求失败';
          wx.showToast({ title: msg, icon: 'none' });
          reject(res.data);
        }
      },
      fail(err) {
        wx.showToast({ title: '网络异常', icon: 'none' });
        reject(err);
      },
    });
  });
}

module.exports = {
  get: (path, data) => request('GET', path, data),
  post: (path, data) => request('POST', path, data),
  put: (path, data) => request('PUT', path, data),
  del: (path, data) => request('DELETE', path, data),
};
