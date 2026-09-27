import path from "node:path";

import type {NextConfig} from "next";

const nextConfig: NextConfig = {
    output: "standalone",
    turbopack: {
        root: path.join(__dirname),
    },
}

module.exports = {
    allowedDevOrigins: ['192.168.1.108'],
}


export default nextConfig;
