import { I } from '../components/icons';

export const NAV = [
  {
    label: "Dashboard", icon: I.home,
    children: [
      { label: "Overview",        icon: I.eye,     path: "/"      },
      { label: "Appraisal Cycle", icon: I.refresh, path: "/cycle" },
    ],
  },
  {
    label: "User Registration", icon: I.users,
    children: [
      { label: "User List",      icon: I.list,    path: "/faculty"           },
      { label: "Add User",       icon: I.addUser, path: "/faculty/add"       },
      { label: "Reset Password", icon: I.lock,    path: "/credentials/reset" },
    ],
  },
  {
    label: "Appraisal", icon: I.star,
    children: [
      { label: "Submission Window", icon: I.doc,   path: "/appraisal/window"   },
      { label: "Submission Status", icon: I.check, path: "/appraisal/status"   },
    ],
  },
  {
    label: "NT Workflow", icon: I.layers,
    children: [
      { label: "Designations",       icon: I.star, path: "/workflow/designations" },
      { label: "Workflow Templates", icon: I.doc,  path: "/workflow/templates"    },
    ],
  },
  {
    label: "Feedback", icon: I.chat,
    children: [
      { label: "Queries & Bugs", icon: I.bug, path: "/feedback" },
    ],
  },
  {
    label: "Announcements", icon: I.bell,
    children: [
      { label: "Create Notice", icon: I.edit, path: "/announcements" },
    ],
  },
  {
    label: "Export Reports", icon: I.dl, adminOnly: true,
    children: [
      { label: "Download CSV", icon: I.dl, path: "/export" },
    ],
  },
  {
    label: "Faculty Authorization", icon: I.shield, adminOnly: true,
    children: [
      { label: "All Scores",      icon: I.eye,   path: "/marks"         },
      { label: "Pending Reviews", icon: I.clock, path: "/marks/pending" },
    ],
  },
  {
    label: "Activity Log", icon: I.list,
    children: [
      { label: "Activity Monitor", icon: I.monitor, path: "/monitoring" },
    ],
  },
  {
    label: "Settings", icon: I.gear,
    children: [
      { label: "System Settings", icon: I.monitor, path: "/settings"          },
      { label: "Security",        icon: I.lock,    path: "/settings/security" },
    ],
  },
  {
    label: "Developer", icon: I.bug, adminOnly: true, superAdminOnly: true,
    children: [
      { label: "Migrate Bucket URLs", icon: I.refresh, path: "/developer/migrate" },
    ],
  },
];
