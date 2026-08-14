import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { PublicLayout } from './components/layout/PublicLayout'
import { DashboardLayout } from './components/layout/DashboardLayout'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { roleHomePath } from './api/auth'
import { LoadingBlock } from './components/ui'

// Role-section pages are route-split (loaded on demand) rather than
// bundled with the initial JS — a buyer never pays for the admin/seller
// bundle weight and vice versa. Landing/login/signup/shell stay eager
// since every visitor hits one of them on first load regardless of role.
const BuyerDashboard = lazy(() => import('./pages/buyer/BuyerDashboard').then((m) => ({ default: m.BuyerDashboard })))
const ProductsBrowsePage = lazy(() =>
  import('./pages/buyer/ProductsBrowsePage').then((m) => ({ default: m.ProductsBrowsePage })),
)
const ProductDetailPage = lazy(() =>
  import('./pages/buyer/ProductDetailPage').then((m) => ({ default: m.ProductDetailPage })),
)
const RecommendationsPage = lazy(() =>
  import('./pages/buyer/RecommendationsPage').then((m) => ({ default: m.RecommendationsPage })),
)
const OrdersPage = lazy(() => import('./pages/buyer/OrdersPage').then((m) => ({ default: m.OrdersPage })))
const WishlistPage = lazy(() => import('./pages/buyer/WishlistPage').then((m) => ({ default: m.WishlistPage })))

const SellerDashboard = lazy(() =>
  import('./pages/seller/SellerDashboard').then((m) => ({ default: m.SellerDashboard })),
)
const ProductsManagePage = lazy(() =>
  import('./pages/seller/ProductsManagePage').then((m) => ({ default: m.ProductsManagePage })),
)
const OrdersManagePage = lazy(() =>
  import('./pages/seller/OrdersManagePage').then((m) => ({ default: m.OrdersManagePage })),
)
const TrustDashboardPage = lazy(() =>
  import('./pages/seller/TrustDashboardPage').then((m) => ({ default: m.TrustDashboardPage })),
)

const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard })))
const UsersPage = lazy(() => import('./pages/admin/UsersPage').then((m) => ({ default: m.UsersPage })))
const TrustMonitoringPage = lazy(() =>
  import('./pages/admin/TrustMonitoringPage').then((m) => ({ default: m.TrustMonitoringPage })),
)
const BlockchainExplorerPage = lazy(() =>
  import('./pages/admin/BlockchainExplorerPage').then((m) => ({ default: m.BlockchainExplorerPage })),
)

const FraudAlertsPage = lazy(() => import('./pages/shared/FraudAlertsPage').then((m) => ({ default: m.FraudAlertsPage })))
const DisputesPage = lazy(() => import('./pages/shared/DisputesPage').then((m) => ({ default: m.DisputesPage })))
const SettingsPage = lazy(() => import('./pages/shared/SettingsPage').then((m) => ({ default: m.SettingsPage })))

function RootRedirect() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <LoadingBlock />
  if (user) return <Navigate to={roleHomePath(user.role)} replace />
  return <LandingPage />
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<LoadingBlock />}>
            <Routes>
              <Route element={<PublicLayout />}>
                <Route index element={<RootRedirect />} />
                <Route path="login" element={<LoginPage />} />
                <Route path="signup" element={<SignupPage />} />
              </Route>

              <Route element={<ProtectedRoute allow={['buyer']} />}>
                <Route path="buyer" element={<DashboardLayout />}>
                  <Route index element={<BuyerDashboard />} />
                  <Route path="products" element={<ProductsBrowsePage />} />
                  <Route path="products/:productId" element={<ProductDetailPage />} />
                  <Route path="recommendations" element={<RecommendationsPage />} />
                  <Route path="orders" element={<OrdersPage />} />
                  <Route path="wishlist" element={<WishlistPage />} />
                  <Route path="fraud-alerts" element={<FraudAlertsPage />} />
                  <Route path="disputes" element={<DisputesPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>
              </Route>

              <Route element={<ProtectedRoute allow={['seller']} />}>
                <Route path="seller" element={<DashboardLayout />}>
                  <Route index element={<SellerDashboard />} />
                  <Route path="products" element={<ProductsManagePage />} />
                  <Route path="orders" element={<OrdersManagePage />} />
                  <Route path="trust" element={<TrustDashboardPage />} />
                  <Route path="fraud-risk" element={<FraudAlertsPage />} />
                  <Route path="disputes" element={<DisputesPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>
              </Route>

              <Route element={<ProtectedRoute allow={['admin']} />}>
                <Route path="admin" element={<DashboardLayout />}>
                  <Route index element={<AdminDashboard />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="fraud" element={<FraudAlertsPage />} />
                  <Route path="disputes" element={<DisputesPage />} />
                  <Route path="trust" element={<TrustMonitoringPage />} />
                  <Route path="blockchain" element={<BlockchainExplorerPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}
