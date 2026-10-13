const { createProxyMiddleware } = require('http-proxy-middleware');

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8081';

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: API_URL,
      changeOrigin: true,
      pathRewrite: {
        '^/api': '/api',
      },
    })
  );

  // Also proxy calls without /api prefix for backend endpoints
  app.use(
    '/auth',
    createProxyMiddleware({
      target: API_URL,
      changeOrigin: true,
    })
  );

  app.use(
    '/message-queue',
    createProxyMiddleware({
      target: API_URL,
      changeOrigin: true,
    })
  );
};
