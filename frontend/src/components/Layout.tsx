import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth, isMod, isAdmin, isVoteOnly, canSubmit, isEmailVerified } from "../auth";

export default function Layout() {
  const { user, logout } = useAuth();

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
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/voting">Vote</NavLink>
            <NavLink to="/submit">Submit</NavLink>
            {user && isVoteOnly(user) && (
              <NavLink to="/submit/upgrade" className="nav-upgrade">
                Unlock Submit
              </NavLink>
            )}
            <NavLink to="/dmca">DMCA</NavLink>
            {isMod(user) && <NavLink to="/mod" className="nav-mod">Mod</NavLink>}
            {isAdmin(user) && <NavLink to="/admin" className="nav-admin">Admin</NavLink>}
            {user ? (
              <>
                <span className="muted">
                  {user.username}
                  {user.reputation_points > 0 && (
                    <> · {user.reputation_points.toFixed(2)} pts</>
                  )}
                  {!canSubmit(user) && user.access_level === "vote_only" ? " (vote only)" : ""}
                </span>
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
    </>
  );
}
