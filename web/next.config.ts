import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: ["pg", "@neondatabase/serverless"],
  // Un sitemap par pays (/sitemap-fr.xml, /sitemap-es.xml), listés par l'index /sitemap.xml.
  async rewrites() {
    return [{ source: "/sitemap-:country.xml", destination: "/api/sitemap/:country" }];
  },
};

export default nextConfig;
