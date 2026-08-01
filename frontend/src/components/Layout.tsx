import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router";
import { api, type MaintenanceWindow } from "../api";
import { useAuth, isMod, isAdmin, isVoteOnly, canSubmit, isEmailVerified } from "../auth";
import { APP_VERSION } from "../version";

function formatWindowRange(window: MaintenanceWindow): string {
  const start = new Date(window.starts_at);
  const end = new Date(window.ends_at);
  const opts: Intl.DateTimeFormatOptions = {
    dateStyle: "medium",
    timeStyle: "short",
  };
  return `${start.toLocaleString(undefined, opts)} → ${end.toLocaleString(undefined, opts)}`;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const [upcoming, setUpcoming] = useState<MaintenanceWindow[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .siteStatus()
      .then((status) => {
        if (!cancelled) setUpcoming(status.maintenance.upcoming ?? []);
      })
      .catch(() => {
        if (!cancelled) setUpcoming([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const nextWindow = upcoming[0] ?? null;

  return (
    <>
      <nav className="navbar">
        <div className="container navbar-inner">
          <Link to="/" className="logo">
            Commercial<span>Brainz</span>
          </Link>
          <div className="nav-links">
            <NavLink to="/browse">Browse</NavLink>
            <NavLink to="/commercials">Commercials</NavLink>
            <NavLink to="/brands">Brands</NavLink>
            <NavLink to="/stores">Stores</NavLink>
            <NavLink to="/services">Services</NavLink>
            <NavLink to="/events">Events</NavLink>
            <NavLink to="/holidays">Holidays</NavLink>
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/voting">Vote</NavLink>
            <NavLink to="/duplicates">Duplicates</NavLink>
            <NavLink to="/submit">Submit</NavLink>
            {user && (user.bulk_submit_enabled || user.can_bulk_submit) && (
              <NavLink to="/submit/bulk">Bulk</NavLink>
            )}
            {user && isVoteOnly(user) && (
              <NavLink to="/submit/upgrade" className="nav-upgrade">
                Unlock Submit
              </NavLink>
            )}
            <NavLink to="/about">About</NavLink>
            <NavLink to="/plugins">Plugins</NavLink>
            <NavLink to="/help">Help</NavLink>
            <NavLink to="/help/basic-usage">Guide</NavLink>
            <NavLink to="/donate">Donate</NavLink>
            <a
              href="https://discord.gg/AEhVjqX4Af"
              target="_blank"
              rel="noreferrer noopener"
            >
              Discord
            </a>
            <a
              href="https://github.com/binarygeek119/CommercialBrainz"
              target="_blank"
              rel="noreferrer noopener"
            >
              GitHub
            </a>
            <NavLink to="/terms">Terms</NavLink>
            <NavLink to="/dmca">DMCA</NavLink>
            {isMod(user) && <NavLink to="/mod" className="nav-mod">Mod</NavLink>}
            {isAdmin(user) && <NavLink to="/admin" className="nav-admin">Admin</NavLink>}
            {user ? (
              <>
                <NavLink to="/account" className="muted">
                  {user.username}
                </NavLink>
                {user.reputation_points > 0 && (
                  <span className="muted"> · {user.reputation_points.toFixed(2)} pts</span>
                )}
                {!canSubmit(user) && user.access_level === "vote_only" ? (
                  <span className="muted"> (vote only)</span>
                ) : null}
                <button className="btn btn-secondary" onClick={logout}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login">Log in</NavLink>
                <NavLink to="/register">Register</NavLink>
              </>
            )}
          </div>
        </div>
      </nav>
      {nextWindow && (
        <div className="maintenance-banner" role="status">
          <div className="container maintenance-banner-inner">
            <span>
              Scheduled maintenance: the site will be offline{" "}
              <strong>{formatWindowRange(nextWindow)}</strong>
              {nextWindow.message ? ` — ${nextWindow.message}` : "."}
            </span>
          </div>
        </div>
      )}
      {user && !isEmailVerified(user) && (
        <div className="verify-banner">
          <div className="container verify-banner-inner">
            <span>
              Verify <strong>{user.email}</strong> to vote and submit edits.
            </span>
            <Link to="/verify-email/pending" className="btn btn-secondary">
              Resend email
            </Link>
          </div>
        </div>
      )}
      <main className="container">
        <Outlet />
      </main>
      <a
        className="version-box"
        href="https://github.com/binarygeek119/CommercialBrainz"
        target="_blank"
        rel="noreferrer noopener"
        aria-label={`CommercialBrainz version ${APP_VERSION} — view source on GitHub`}
        title="View source on GitHub"
      >
        v{APP_VERSION}
      </a>
    </>
  );
}
