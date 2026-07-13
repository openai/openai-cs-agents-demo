import { redirect } from "next/navigation";

export default function Home() {
  const defaultSurface = process.env.NEXT_PUBLIC_DEFAULT_APP_SURFACE;
  redirect(defaultSurface === "admin" ? "/admin/workspace" : "/support");
}
