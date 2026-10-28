import "./globals.css";

export const metadata = {
  title: "Transcript pipeline demo",
  description: "Change pipeline config through the API and see the results move.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
