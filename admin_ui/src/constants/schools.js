// Single source of truth for all school data.
// Import from here instead of re-defining in each page.

export const SCHOOLS = [
  { code: 'SoCSEA', full: 'School of Computer Science & Applications',       dean: 'engineering',     hod: false },
  { code: 'SoBB',   full: 'School of Bio-Engineering & Bio Science',          dean: 'engineering',     hod: false },
  { code: 'SoCE',   full: 'School of Continual Education',                    dean: 'engineering',     hod: false },
  { code: 'SoEMR',  full: 'School of Engineering, Management & Research',     dean: 'engineering',     hod: true  },
  { code: 'SoCM',   full: 'School of Commerce & Management',                  dean: 'non_engineering', hod: false },
  { code: 'SoMCS',  full: 'School of Media & Communication Studies',          dean: 'non_engineering', hod: false },
  { code: 'SoHSS',  full: 'School of Humanities and Social Sciences',          dean: 'non_engineering', hod: false },
  { code: 'SoD',    full: 'School of Design',                                 dean: 'non_engineering', hod: false },
  { code: 'SoAA',   full: 'School of Applied Arts',                           dean: 'non_engineering', hod: false },
  { code: 'CISR',   full: 'Center for Interdisciplinary Studies & Research',  dean: 'cisr',            hod: false },
];

export const ENGG_SCHOOLS     = SCHOOLS.filter(s => s.dean === 'engineering');
export const NON_ENGG_SCHOOLS = SCHOOLS.filter(s => s.dean === 'non_engineering');
export const TEACHING_SCHOOLS = SCHOOLS.filter(s => s.dean !== 'cisr');

// Just the codes — useful for plain <select> lists
export const ALL_SCHOOL_CODES       = SCHOOLS.map(s => s.code);
export const ENGG_SCHOOL_CODES      = ENGG_SCHOOLS.map(s => s.code);
export const NON_ENGG_SCHOOL_CODES  = NON_ENGG_SCHOOLS.map(s => s.code);
export const TEACHING_SCHOOL_CODES  = TEACHING_SCHOOLS.map(s => s.code);

// code → full name lookup
export const SCHOOL_MAP = Object.fromEntries(SCHOOLS.map(s => [s.code, s.full]));

// Richer per-school metadata used by AppraisalCyclePage
const DEAN_LABEL = {
  engineering:     'Dean of Engineering',
  non_engineering: 'Dean of Non-Engineering',
  cisr:            'VC (direct)',
};
export const SCHOOL_META = Object.fromEntries(
  SCHOOLS.map(s => [s.code, {
    full:   s.full,
    dean:   DEAN_LABEL[s.dean],
    hasHod: s.hod,
    track:  s.dean,
  }])
);

export const SOEMR_DEPTS = [
  'Mechanical Engineering',
  'Civil Engineering',
  'Chemical Engineering',
  'Semiconductor Engineering',
];
