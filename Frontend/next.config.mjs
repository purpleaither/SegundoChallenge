// Endereço da API Python (rag/api.py). O Next repassa /api/* para lá, então o navegador
// fala só com o próprio frontend e não há problema de CORS.
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Gera um servidor enxuto em .next/standalone, usado pela imagem Docker
  output: 'standalone',
  // O padrão do proxy é 30 s; o Ollama em CPU (Docker) pode demorar mais que isso
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${BACKEND_URL}/api/:path*` }]
  },
}

export default nextConfig
