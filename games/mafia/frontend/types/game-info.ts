export interface RoleInfo {
  key: string;
  display_name: string;
  team: string;
  description: string;
  example: string;
  acts_at_night: boolean;
  allow_self_target: boolean;
  hostile: boolean;
  max_uses: number | null;
  mutually_exclusive_with: string[];
}

export interface PhaseInfo {
  key: string;
  name: string;
  summary: string;
  details: string;
  example: string;
}

export interface TieBreakerOption {
  key: string;
  label: string;
  description: string;
  example: string;
}

export interface TieBreakerInfo {
  key: string;
  title: string;
  description: string;
  options: TieBreakerOption[];
}

export interface RuleSection {
  title: string;
  body: string;
  example: string | null;
}

export interface FaqEntry {
  question: string;
  answer: string;
}

export interface GameInfo {
  roles: RoleInfo[];
  phases: PhaseInfo[];
  tie_breakers: TieBreakerInfo[];
  rules: RuleSection[];
  faq: FaqEntry[];
}
