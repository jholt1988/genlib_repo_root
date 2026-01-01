export const metadata = {
  title: "genlib-web",
  description: "Stacks & agents UI for genlib"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "ui-sans-serif, system-ui", margin: 0 }}>
        <div style={{ padding: 16, borderBottom: "1px solid #222" }}>
          <a href="/" style={{ marginRight: 12 }}>Stacks</a>
          <a href="/agent" style={{ marginRight: 12 }}>Agent</a>
          <a href="/jobs" style={{ marginRight: 12 }}>Jobs</a>
          <a href="/gallery">Gallery</a>
        </div>
        <div style={{ padding: 16 }}>{children}</div>
      </body>
    </html>
  );
}
