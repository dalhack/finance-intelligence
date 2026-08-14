import 'package:dio/dio.dart';
import '../org_context.dart';

/// Attaches the active organization id required by the backend's
/// execution-context dependency. The bootstrap endpoint itself does not
/// require the header, so a null OrgContext simply omits it.
class OrganizationInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final orgId = OrgContext.organizationId;
    if (orgId != null && orgId.isNotEmpty) {
      options.headers['X-Organization-ID'] = orgId;
    }
    handler.next(options);
  }
}
