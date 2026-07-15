import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  experimental: {
    // El cliente de Postgres no debe ser empaquetado por el bundler de servidor.
    serverComponentsExternalPackages: ["postgres"],
  },
};

export default withNextIntl(nextConfig);
