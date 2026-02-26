/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    async rewrites() {
        // 런타임에 환경 변수를 읽도록 설정
        const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

        // 이 로그는 서버 기동 시 터미널에 출력됩니다.
        console.log(`\x1b[36m[NextConfig] Backend Proxy initialized:\x1b[0m ${backendUrl}`);

        return [
            {
                source: '/api/:path*',
                destination: `${backendUrl}/api/:path*`,
            },
        ];
    },
};

export default nextConfig;
