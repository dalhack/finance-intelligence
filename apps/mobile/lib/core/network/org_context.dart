/// Process-wide holder for the active organization id.
/// Set once after sign-in (via POST /organizations/bootstrap) and read by
/// [OrganizationInterceptor] on every request. Development builds seed a
/// fixed synthetic id in main(), matching the backend's dev adapter which
/// accepts any organization UUID.
class OrgContext {
  static String? organizationId;
}
