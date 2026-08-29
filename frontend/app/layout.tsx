import "./styles.css";

export const metadata = { title: "ConsulTax | Personal tax clarity", description: "Rules-led Indian tax planning with transparent reasoning." };

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
