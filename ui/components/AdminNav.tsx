"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { usePathname } from "next/navigation";

interface AdminNavProps {
  variant?: "top" | "compact";
}

export function AdminNav({ variant = "top" }: AdminNavProps) {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "← Home", external: false },
    { href: "/admin", label: "Dashboard", external: false },
    { href: "/admin/load-test", label: "Load Testing", external: false },
    { href: "http://localhost:8001/batch-dashboard", label: "Batch Monitoring", external: true },
    { href: "http://localhost:9000/dashboard/", label: "Meta Monitoring", external: true },
    { href: "/maintenance?preview=true", label: "Maintenance Page", external: false },
  ];

  return (
    <nav className="flex flex-wrap gap-2" aria-label="Admin navigation">
      {links.map((link) => {
        const isActive = !link.external && pathname === link.href;

        if (link.external) {
          return (
            <Button
              key={link.href}
              variant="outline"
              size="sm"
              onClick={() => window.open(link.href, "_blank")}
            >
              {link.label}
            </Button>
          );
        }

        return (
          <Link key={link.href} href={link.href}>
            <Button
              variant={isActive ? "default" : "outline"}
              size="sm"
              disabled={isActive}
            >
              {link.label}
            </Button>
          </Link>
        );
      })}
    </nav>
  );
}
