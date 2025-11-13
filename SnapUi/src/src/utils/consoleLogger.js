/**
 * Console Logger Utility
 * Intercepts and stores browser console logs for later retrieval
 */

class ConsoleLogger {
  constructor() {
    this.logs = [];
    this.maxLogs = 100; // Keep last 100 logs
    this.originalConsole = {
      log: console.log,
      error: console.error,
      warn: console.warn,
      info: console.info,
      debug: console.debug
    };
    this.init();
  }

  init() {
    // Intercept console methods
    const self = this;
    
    console.log = function(...args) {
      self.addLog('log', args);
      self.originalConsole.log.apply(console, args);
    };

    console.error = function(...args) {
      self.addLog('error', args);
      self.originalConsole.error.apply(console, args);
    };

    console.warn = function(...args) {
      self.addLog('warn', args);
      self.originalConsole.warn.apply(console, args);
    };

    console.info = function(...args) {
      self.addLog('info', args);
      self.originalConsole.info.apply(console, args);
    };

    console.debug = function(...args) {
      self.addLog('debug', args);
      self.originalConsole.debug.apply(console, args);
    };
  }

  addLog(level, args) {
    const timestamp = new Date().toISOString();
    const message = args.map(arg => {
      if (typeof arg === 'object') {
        try {
          return JSON.stringify(arg, null, 2);
        } catch (e) {
          return String(arg);
        }
      }
      return String(arg);
    }).join(' ');

    this.logs.push({
      timestamp,
      level,
      message
    });

    // Keep only the last maxLogs entries
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }
  }

  getLastLogs(count = 10) {
    return this.logs.slice(-count);
  }

  getAllLogs() {
    return [...this.logs];
  }

  clearLogs() {
    this.logs = [];
  }
}

// Create a singleton instance
const consoleLogger = new ConsoleLogger();

export default consoleLogger;

