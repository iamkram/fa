import { ClientDetail } from "@/components/ClientDetail";

export default function ClientDetailPage({
  params,
}: {
  params: { accountId: string };
}) {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <ClientDetail accountId={params.accountId} />
      </div>
    </div>
  );
}
