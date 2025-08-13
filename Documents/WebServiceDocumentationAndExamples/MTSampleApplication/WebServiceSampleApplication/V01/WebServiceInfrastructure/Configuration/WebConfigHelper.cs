namespace WebServiceInfrastructure.Configuration
{
    public static class WebConfigHelper
    {
        // "localhost" must be replaced by the IP of the balance
        private const string Url = "http://localhost:8080/MT/Laboratory/Balance/XprXsr/V01";

        // Balance -> Settings -> LabX/Services -> Web service configuration -> Client password
        public const string ClientPassword = "12345678";

        public static WebConfig CreateWebConfig()
        {
            var webConfig = new WebConfig(Url, ClientPassword);
            return webConfig;
        }
    }
}
