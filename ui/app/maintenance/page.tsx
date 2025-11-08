export default function MaintenancePage() {
  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="text-center max-w-md px-4">
        <h1 className="text-4xl font-bold mb-4">Under Maintenance</h1>
        <p className="text-muted-foreground mb-6">
          The FA AI Assistant is currently undergoing scheduled maintenance.
          We'll be back online shortly.
        </p>
        <p className="text-sm text-muted-foreground">
          For urgent inquiries, please contact support@example.com
        </p>
      </div>
    </div>
  );
}
