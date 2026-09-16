/**
 * PM2 Ecosystem Configuration
 * Production-ready process management for WROS frontend & backend
 *
 * Usage:
 *   pm2 start ecosystem.config.js          # Start all processes
 *   pm2 monit                              # Monitor all processes
 *   pm2 logs                               # View all logs
 *   pm2 save && pm2 startup               # Enable auto-startup on reboot
 */

module.exports = {
  apps: [
    {
      // ============================================================
      // BACKEND: Python Uvicorn Server
      // ============================================================
      name: "wros-backend",
      script: "python",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 8081",
      cwd: "./backend",

      // Process Management
      instances: 1,
      exec_mode: "fork",

      // Auto-restart on crash
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      max_memory_restart: "1G",

      // Environment
      env: {
        ENVIRONMENT: "production",
        NODE_ENV: "production"
      },

      // Logging
      error_file: "./logs/backend-error.log",
      out_file: "./logs/backend-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",

      // Health Check
      listen_timeout: 10000,
      kill_timeout: 5000,

      // Watch for changes in development
      watch: false,
      ignore_watch: ["node_modules", "logs", ".git"],
    },

    {
      // ============================================================
      // FRONTEND: React Development Server (npm start)
      // ============================================================
      name: "wros-frontend",
      script: "npm",
      args: "start",
      cwd: "./frontend",

      // Process Management
      instances: 1,
      exec_mode: "fork",

      // Auto-restart on crash
      autorestart: true,
      max_restarts: 10,
      min_uptime: "15s",
      max_memory_restart: "1G",

      // Environment
      env: {
        REACT_APP_API_URL: "http://localhost:8081",
        NODE_ENV: "production"
      },

      // Logging
      error_file: "./logs/frontend-error.log",
      out_file: "./logs/frontend-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",

      // Health Check
      listen_timeout: 15000,
      kill_timeout: 5000,
    }
  ],

  // ============================================================
  // Global Settings
  // ============================================================
  deploy: {
    production: {
      user: "app",
      host: "your-server.com",
      ref: "origin/main",
      repo: "git@github.com:your-org/WROS-Master.git",
      path: "/var/www/wros",
      "post-deploy": "npm install && pm2 restart ecosystem.config.js --env production"
    }
  },

  // Monitor settings
  monitor_delay: 5000,

  // Graceful shutdown
  kill_timeout: 5000
};
