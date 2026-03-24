/**
 * /landing-view/page.jsx
 * Internal route — never seen in the browser URL bar.
 * Middleware rewrites "/" → "/landing-view" for logged-out users.
 * Renders the full landing page inside the Privy provider context.
 */
import LandingPage from '../landing/LandingPage';

export default function LandingViewPage() {
  return <LandingPage />;
}
