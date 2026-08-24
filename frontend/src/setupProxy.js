const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Proxy all API requests to backend running on port 8080
  app.use(
    '/rbac',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
      pathRewrite: {
        '^/rbac': '/rbac'
      }
    })
  );

  app.use(
    '/hr',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
      pathRewrite: {
        '^/hr': '/hr'
      }
    })
  );

  app.use(
    '/auth',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
      pathRewrite: {
        '^/auth': '/auth'
      }
    })
  );
};
