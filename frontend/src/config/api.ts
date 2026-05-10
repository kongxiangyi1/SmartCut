const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001',
  WS_URL: import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8001',
  API_VERSION: '/api/v1',

  get fullApiUrl() {
    return `${this.BASE_URL}${this.API_VERSION}`
  },

  get fullWsUrl() {
    return `${this.WS_URL}${this.API_VERSION}`
  }
}

export default API_CONFIG