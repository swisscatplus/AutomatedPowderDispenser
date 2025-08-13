namespace WebServiceInfrastructure
{
    using MT.Laboratory.Balance.XprXsr.V02;
    using System;

    public class Session : IDisposable
    {
        private SessionServiceClient _sessionServiceClient;
        private volatile bool _disposed;

        public Session(WebConfig webConfig)
        {
            // create session client
            _sessionServiceClient = webConfig.CreateClient<SessionServiceClient>();
            
            // open session
            var openSessionResponse = _sessionServiceClient.OpenSession(new OpenSessionRequest());
            SessionId = CryptographyHelper.DecryptSessionId(webConfig.Password, openSessionResponse.SessionId, openSessionResponse.Salt);
        }

        public string SessionId { get; private set; }

        public void CancelAll()
        {
            _sessionServiceClient.Cancel(new CancelRequest(SessionId, CancelType.All, null));
        }

        /// <inheritdoc />
        public void Dispose()
        {
            if (!_disposed)
            {
                _disposed = true;
                if (!_disposed)
                {
                    CancelAll();
                    _sessionServiceClient.CloseSession(new CloseSessionRequest(SessionId));
                    SessionId = null;
                    _sessionServiceClient = null;
                }
            }
        }
    }
}
