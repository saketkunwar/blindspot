import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
import ThemeToggle from "../components/ThemeToggle";

export const metadata = { title: "BlindSpot console" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="light"><ThemeToggle />{children}</body>
    </html>
  );
}
