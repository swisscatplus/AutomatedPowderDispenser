namespace Weighing
{
    using MT.Laboratory.Balance.XprXsr.V03;
    using System.Linq;
    using WebServiceInfrastructure;
    using WebServiceInfrastructure.Configuration;

    public class Program
    {
        private static void Main(string[] args)
        {
            if (args.Length == 0 || args.Contains("GetWeighingValues"))
            {
                RunGetWeighingValuesSample();
            }

            if (args.Contains("Zero"))
            {
                RunZeroSample();
            }
        }

        private static void RunZeroSample()
        {
            // configure ip/password inside the web config helper class
            var webConfig = WebConfigHelper.CreateWebConfig();

            // init service clients
            var weighingServiceClient = webConfig.CreateClient<WeighingServiceClient>();

            using (var session = new Session(webConfig))
            {
                WeighingService.Zero(session.SessionId, weighingServiceClient);
                Logger.Finish();
            }
        }

        private static void RunGetWeighingValuesSample()
        {
            // configure ip/password inside the web config helper class
            var webConfig = WebConfigHelper.CreateWebConfig();

            // init service clients
            var weighingServiceClient = webConfig.CreateClient<WeighingServiceClient>();
            var weighingTaskServiceClient = webConfig.CreateClient<WeighingTaskServiceClient>();

            using (var session = new Session(webConfig))
            {
                WeighingService.GetWeightValues(session.SessionId, weighingServiceClient, weighingTaskServiceClient);
                Logger.Finish();
            }
        }
    }
}