namespace Authentication
{
    using MT.Laboratory.Balance.XprXsr.V02;
    using WebServiceInfrastructure;
    using WebServiceInfrastructure.Configuration;

    class Program
    {
        static void Main()
        {
            RunLoginUser();
        }

        private static void RunLoginUser()
        {
            const string UserName = "User1";
            const string UserPassword = "abcd";

            var webConfig = WebConfigHelper.CreateWebConfig();
            var authenticationServiceClient = webConfig.CreateClient<AuthenticationServiceClient>();

            using (var session = new Session(webConfig))
            {
                var encryptedPassword = CryptographyHelper.EncryptPassword(UserPassword, WebConfigHelper.ClientPassword, session.SessionId);

                var loginUserRequest = new LoginUserRequest
                {
                    SessionId = session.SessionId,
                    LoginCredentials = new LoginCredentials
                    {
                        UserName = UserName,
                        EncryptedPassword = encryptedPassword
                    }
                };
                authenticationServiceClient.LoginUser(loginUserRequest);

                Logger.Finish();
            }
        }
    }
}
