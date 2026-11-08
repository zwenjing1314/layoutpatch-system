import type { AccountResponse } from "@/lib/api/generated";

export type AccountAction = "create" | "enable" | "disable" | "reset" | "revoke";
export type AccountIntent = { action: AccountAction; target: AccountResponse | null };
export const accountActionLabel: Record<AccountAction, string> = {
  create: "创建账号", enable: "启用账号", disable: "停用账号", reset: "重置密码", revoke: "撤销全部会话",
};

export function accountImpact(intent: AccountIntent, selfId: string) {
  const self = intent.target?.user_id === selfId;
  const messages: Record<AccountAction, string> = {
    create: "新账号立即启用。首次登录后必须设置新密码；请通过安全渠道向使用者交付初始密码。",
    enable: "账号可以重新登录，之前已失效的会话不会恢复。",
    disable: "账号将无法登录，全部现有会话立即失效。该操作保留文档，不会删除账号。",
    reset: "全部现有会话立即失效。使用新临时密码重新登录后，必须再次设置新密码。",
    revoke: "全部现有会话立即失效，需要重新登录；密码及首改要求保持不变。",
  };
  return messages[intent.action] + (self && intent.action !== "enable" ? " 这是你当前的账号，成功后会退出当前工作台。" : "");
}

/** Only fixed public messages; never interpolate a server body or password. */
export function accountFailure(error: { status?: number; body?: unknown } | null) {
  const detail = (error?.body as { detail?: string } | undefined)?.detail;
  if (error?.status === 409 && detail === "LAST_ACTIVE_ADMIN") return "不能停用最后一个启用的管理员。请先创建并启用另一管理员。";
  if (error?.status === 409 && detail === "USERNAME_EXISTS") return "账号已存在，请更换账号名称。";
  if (error?.status === 404) return "账号不存在或已变化，请刷新列表后核对。";
  if (error?.status === 422) return "输入不符合要求，请检查账号、角色和密码长度。";
  if (error?.status === 403) return "当前操作未获授权，请重新确认登录状态。";
  return "操作结果尚未确认。请先刷新列表核对，重置或撤销操作不要直接重复提交。";
}
