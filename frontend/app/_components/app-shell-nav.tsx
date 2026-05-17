"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/campaigns", label: "Campaign Lab" },
  { href: "/queue", label: "Render Queue" },
];

function isActive(pathname: string, href: string) {
  if (pathname === href) {
    return true;
  }

  if (href !== "/dashboard" && pathname.startsWith(`${href}/`)) {
    return true;
  }

  return href === "/dashboard" && pathname === "/";
}

export function AppShellNav() {
  const pathname = usePathname();

  return (
    <nav className="sidebar-nav" aria-label="Primary">
      {navItems.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={isActive(pathname, item.href) ? "active" : undefined}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
