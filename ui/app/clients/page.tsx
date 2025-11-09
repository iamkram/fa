import { ClientList } from "@/components/ClientList";

export default function ClientsPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            Client Portfolio Management
          </h1>
          <p className="text-muted-foreground">
            View and manage your client portfolios and holdings
          </p>
        </div>
        <ClientList />
      </div>
    </div>
  );
}
