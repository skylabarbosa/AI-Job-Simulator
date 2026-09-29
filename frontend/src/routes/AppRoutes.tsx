import { Navigate, Route, Routes } from 'react-router-dom'

import { LoginPage } from '../pages/LoginPage'
import { SignupPage } from '../pages/SignupPage'
import { AuthenticatedPage } from '../pages/AuthenticatedPage'
import { UnauthorizedPage } from '../pages/UnauthorizedPage'
import { BusinessProjectsPage } from '../pages/BusinessProjectsPage'
import { NewProjectPage } from '../pages/NewProjectPage'
import { ProjectDetailPage } from '../pages/ProjectDetailPage'
import { LearnerProjectsPage } from '../pages/LearnerProjectsPage'
import { LearnerProjectOverviewPage } from '../pages/LearnerProjectOverviewPage'
import { LearnerStartedTaskWorkspacePage } from '../pages/LearnerTaskWorkspacePage'
import { LearnerProgressPage } from '../pages/LearnerProgressPage'
import { LearnerSkillsPage } from '../pages/LearnerSkillsPage'
import { ProtectedRoute } from './ProtectedRoute'
import { LearnerAppShell } from '../components/LearnerAppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AuthenticatedPage />} />
      </Route>
      <Route element={<ProtectedRoute roles={['admin']} />}>
        <Route path="/admin" element={<AuthenticatedPage />} />
      </Route>
      <Route element={<ProtectedRoute roles={['business', 'admin']} />}>
        <Route path="/business/projects" element={<BusinessProjectsPage />} />
        <Route path="/business/projects/new" element={<NewProjectPage />} />
        <Route path="/business/projects/:projectId" element={<ProjectDetailPage />} />
      </Route>
      <Route element={<ProtectedRoute roles={['learner']} />}>
        <Route element={<LearnerAppShell />}>
          <Route path="/learner/projects" element={<LearnerProjectsPage />} />
          <Route path="/learner/progress" element={<LearnerProgressPage />} />
          <Route path="/learner/skills" element={<LearnerSkillsPage />} />
          <Route path="/learner/projects/:projectId" element={<LearnerProjectOverviewPage />} />
          <Route
            path="/learner/projects/:projectId/tasks/:taskId/workspace"
            element={<LearnerStartedTaskWorkspacePage />}
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

