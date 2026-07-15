import { getTranslations } from "next-intl/server";

export default async function NotFound() {
  const t = await getTranslations("search");
  return (
    <>
      <h1>404</h1>
      <p>{t("noResults")}</p>
      <p>
        <a href="/">{t("submit")} →</a>
      </p>
    </>
  );
}
