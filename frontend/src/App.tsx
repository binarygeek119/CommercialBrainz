import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import BrowsePage from "./pages/BrowsePage";
import BrandsPage from "./pages/BrandsPage";
import CommercialsPage from "./pages/CommercialsPage";
import SearchPage from "./pages/SearchPage";
import VideoPage from "./pages/VideoPage";
import CommercialPage from "./pages/CommercialPage";
import AdvertiserPage from "./pages/AdvertiserPage";
import SubmitPage from "./pages/SubmitPage";
import SubmitUpgradePage from "./pages/SubmitUpgradePage";
import VotingPage from "./pages/VotingPage";
import EditsPage from "./pages/EditsPage";
import EditDetailPage from "./pages/EditDetailPage";
import DMCAPage from "./pages/DMCAPage";
import ModPage from "./pages/ModPage";
import ModRoute from "./components/ModRoute";
import AdminPage from "./pages/AdminPage";
import AdminRoute from "./components/AdminRoute";
import LoginPage from "./pages/LoginPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import VerifyEmailPendingPage from "./pages/VerifyEmailPendingPage";
import UserProfilePage from "./pages/UserProfilePage";
import RegisterPage from "./pages/RegisterPage";
import DevSiteDisclaimer from "./components/DevSiteDisclaimer";

export default function App() {
  return (
    <>
      <DevSiteDisclaimer />
      <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="browse" element={<BrowsePage />} />
        <Route path="brands" element={<BrandsPage />} />
        <Route path="commercials" element={<CommercialsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="video/:sbid" element={<VideoPage />} />
        <Route path="commercial/:sbid" element={<CommercialPage />} />
        <Route path="advertiser/:sbid" element={<AdvertiserPage />} />
        <Route path="submit" element={<SubmitPage />} />
        <Route path="submit/upgrade" element={<SubmitUpgradePage />} />
        <Route path="edits" element={<EditsPage />} />
        <Route path="edits/:id" element={<EditDetailPage />} />
        <Route path="user/:username" element={<UserProfilePage />} />
        <Route path="voting" element={<VotingPage />} />
        <Route path="dmca" element={<DMCAPage />} />
        <Route element={<ModRoute />}>
          <Route path="mod" element={<ModPage />} />
        </Route>
        <Route element={<AdminRoute />}>
          <Route path="admin" element={<AdminPage />} />
        </Route>
        <Route path="login" element={<LoginPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="verify-email" element={<VerifyEmailPage />} />
        <Route path="verify-email/pending" element={<VerifyEmailPendingPage />} />
        <Route path="register" element={<RegisterPage />} />
      </Route>
    </Routes>
    </>
  );
}
