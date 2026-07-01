import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth, isMod, isAdmin, isVoteOnly, canSubmit } from "../auth";

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
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/submit">Submit</NavLink>
            {user && isVoteOnly(user) && (
              <NavLink to="/submit/upgrade" className="nav-upgrade">
                Unlock Submit
              </NavLink>
            )}
            <NavLink to="/edits">Open Edits</NavLink>
            <NavLink to="/dmca">DMCA</NavLink>
            {isMod(user) && <NavLink to="/mod">Mod Queue</NavLink>}
            {isAdmin(user) && <NavLink to="/admin" className="nav-admin">Admin</NavLink>}
            {user ? (
              <>
                <span className="muted">
                  {user.username}
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
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
