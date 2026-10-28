import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";

export const metadata = { title: "BlindSpot console" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
