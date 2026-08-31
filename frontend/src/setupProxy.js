const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Proxy all API requests to backend running on port 8080
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  app.use(
    '/auth',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/auth': '/api/v1/auth',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/rbac',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  app.use(
    '/hr',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  app.use(
    '/candidates',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  app.use(
    '/jobs',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  app.use(
    '/queues',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/queues': '/api/v1/queues',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/onboarding',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      changeOrigin: true,
    })
  );

  // Route remaining API endpoints to /api/v1
  app.use(
    '/interviews',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/interviews': '/api/v1/interviews',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/offer-letter',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/offer-letter': '/api/v1/offer-letter',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/status',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/status': '/api/v1/status',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/activity-feed',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/activity-feed': '/api/v1/activity-feed',
      },
      changeOrigin: true,
    })
  );

  app.use(
    '/notifications',
    createProxyMiddleware({
      target: 'http://localhost:8080',
      pathRewrite: {
        '^/notifications': '/api/v1/notifications',
      },
      changeOrigin: true,
    })
  );
};
