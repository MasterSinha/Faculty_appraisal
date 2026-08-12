import { lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layout/MainLayout'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'
import MigrateBucketPage from './pages/developer/MigrateBucketPage'
import BackupPage from './pages/developer/BackupPage'
import TransitionPage from './pages/developer/TransitionPage'
import { api } from './api/client'

const ExperimentalSandboxPage = lazy(() => import('./pages/developer/ExperimentalSandboxPage'))


// ── Lazy-loaded pages — each splits into its own JS chunk ──────────────────────
const OverviewPage          = lazy(() => import('./pages/dashboard/OverviewPage'))
const AppraisalCyclePage    = lazy(() => import('./pages/dashboard/AppraisalCyclePage'))

const FacultyListPage       = lazy(() => import('./pages/faculty/FacultyListPage'))
const AddFacultyPage        = lazy(() => import('./pages/faculty/AddFacultyPage'))

const SubmissionWindowPage  = lazy(() => import('./pages/appraisal/SubmissionWindowPage'))
const SubmissionStatusPage  = lazy(() => import('./pages/appraisal/SubmissionStatusPage'))

const SubmittedFacultyPage  = lazy(() => import('./pages/tracking/SubmittedFacultyPage'))
const PendingFacultyPage    = lazy(() => import('./pages/tracking/PendingFacultyPage'))
const SchoolStatisticsPage  = lazy(() => import('./pages/tracking/SchoolStatisticsPage'))

const CredentialDetailsPage = lazy(() => import('./pages/credentials/CredentialDetailsPage'))

const DesignationsPage      = lazy(() => import('./pages/workflow/DesignationsPage'))
const WorkflowTemplatesPage = lazy(() => import('./pages/workflow/WorkflowTemplatesPage'))

const FeedbackPage          = lazy(() => import('./pages/feedback/FeedbackPage'))
const AnnouncementsPage     = lazy(() => import('./pages/announcements/AnnouncementsPage'))
const SettingsPage          = lazy(() => import('./pages/settings/SettingsPage'))
const SecurityPage          = lazy(() => import('./pages/settings/SecurityPage'))

const FacultyMarksPage      = lazy(() => import('./pages/marks/FacultyMarksPage'))
const PendingReviewsPage    = lazy(() => import('./pages/marks/PendingReviewsPage'))

const ExportReportPage      = lazy(() => import('./pages/export/ExportReportPage'))
const EditProfilePage       = lazy(() => import('./pages/profile/EditProfilePage'))
const HistoryPage           = lazy(() => import('./pages/history/HistoryPage'))
const MonitoringPage        = lazy(() => import('./pages/monitoring/MonitoringPage'))

export default function App() {
  const profile = api.getProfile();
  const isExperimental = profile?.email === 'experimental@gmail.com';

  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<RequireAuth />}>
        {/* MainLayout contains the Suspense boundary for all lazy pages */}
        <Route path="/" element={<MainLayout />}>
          <Route index                      element={<OverviewPage />}         />
          <Route path="cycle"               element={<AppraisalCyclePage />}   />

          <Route path="faculty"             element={<FacultyListPage />}      />
          <Route path="faculty/add"         element={<AddFacultyPage />}       />

          <Route path="appraisal/window"    element={<SubmissionWindowPage />} />
          <Route path="appraisal/status"    element={<SubmissionStatusPage />} />

          <Route path="tracking/submitted"  element={<SubmittedFacultyPage />} />
          <Route path="tracking/pending"    element={<PendingFacultyPage />}   />
          <Route path="tracking/schools"    element={<SchoolStatisticsPage />} />

          <Route path="credentials/reset"   element={<CredentialDetailsPage />} />

          <Route path="workflow/designations" element={<DesignationsPage />}      />
          <Route path="workflow/templates"    element={<WorkflowTemplatesPage />} />

          <Route path="analytics"           element={<Navigate to="/" replace />} />

          <Route path="feedback"            element={<FeedbackPage />}         />
          <Route path="announcements"       element={<AnnouncementsPage />}    />

          <Route path="settings"            element={<SettingsPage />}         />
          <Route path="settings/security"   element={<SecurityPage />}         />
          
          <Route path="developer/migrate"   element={<MigrateBucketPage />}    />
          <Route path="developer/backup"    element={<BackupPage />}           />
          <Route path="developer/transition" element={<TransitionPage />}      />
          {isExperimental && (
            <Route path="developer/sandbox"   element={<ExperimentalSandboxPage />} />
          )}

          <Route path="marks"               element={<FacultyMarksPage />}     />
          <Route path="marks/pending"       element={<PendingReviewsPage />}   />

          <Route path="export"              element={<ExportReportPage />}     />
          <Route path="profile"             element={<EditProfilePage />}      />
          <Route path="history"             element={<HistoryPage />}          />
          <Route path="monitoring"          element={<MonitoringPage />}       />

          <Route path="*"                   element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
