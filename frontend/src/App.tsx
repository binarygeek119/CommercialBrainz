import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import BrowsePage from "./pages/BrowsePage";
import SearchPage from "./pages/SearchPage";
import VideoPage from "./pages/VideoPage";
import CommercialPage from "./pages/CommercialPage";
import AdvertiserPage from "./pages/AdvertiserPage";
import SubmitPage from "./pages/SubmitPage";
import SubmitUpgradePage from "./pages/SubmitUpgradePage";
import EditsPage from "./pages/EditsPage";
import EditDetailPage from "./pages/EditDetailPage";
import DMCAPage from "./pages/DMCAPage";
import ModQueuePage from "./pages/ModQueuePage";
import AdminPage from "./pages/AdminPage";
import AdminRoute from "./components/AdminRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="browse" element={<BrowsePage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="video/:sbid" element={<VideoPage />} />
        <Route path="commercial/:sbid" element={<CommercialPage />} />
        <Route path="advertiser/:sbid" element={<AdvertiserPage />} />
        <Route path="submit" element={<SubmitPage />} />
        <Route path="submit/upgrade" element={<SubmitUpgradePage />} />
        <Route path="edits" element={<EditsPage />} />
        <Route path="edits/:id" element={<EditDetailPage />} />
        <Route path="dmca" element={<DMCAPage />} />
        <Route path="mod" element={<ModQueuePage />} />
        <Route element={<AdminRoute />}>
          <Route path="admin" element={<AdminPage />} />
        </Route>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
      </Route>
    </Routes>
  );
}
