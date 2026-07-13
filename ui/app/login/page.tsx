import { redirect } from "next/navigation";
import { adminLoginPageUrl, safeReturnTo } from "@/lib/auth";

type LoginRedirectProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function LoginRedirect({ searchParams }: LoginRedirectProps) {
  const params = (await searchParams) ?? {};
  redirect(
    adminLoginPageUrl(
      safeReturnTo(firstParam(params.return_to)),
      firstParam(params.reason),
    ),
  );
}
