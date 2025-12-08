namespace Session
{
    using WebServiceInfrastructure;
    using WebServiceInfrastructure.Configuration;

    class Program
    {
        private static void Main()
        {
            RunCancelAllSample();
        }

        private static void RunCancelAllSample()
        {
            // configure ip/password inside the web config helper class
            var webConfig = WebConfigHelper.CreateWebConfig();

            using (var session = new Session(webConfig))
            {
                Logger.Trace("Start cancel all...");
                session.CancelAll();
                Logger.Trace("Cancel all success.");
                Logger.Finish();
            }
        }
    }
}
