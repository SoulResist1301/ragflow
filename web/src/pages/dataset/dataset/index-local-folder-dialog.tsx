import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';
import { IIndexLocalFolderFormData } from './use-index-local-folder';

const formSchema = z.object({
  localPath: z.string().min(1, {
    message: 'knowledgeDetails.localFolderPathRequired',
  }),
  recursive: z.boolean().default(true),
  parseOnCreation: z.boolean().default(true),
});

interface IndexLocalFolderDialogProps {
  visible: boolean;
  hideModal: () => void;
  onOk: (data: IIndexLocalFolderFormData) => Promise<number | undefined>;
  loading: boolean;
}

export function IndexLocalFolderDialog({
  visible,
  hideModal,
  onOk,
  loading,
}: IndexLocalFolderDialogProps) {
  const { t } = useTranslation();

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      localPath: '/ragflow/mounted_data',
      recursive: true,
      parseOnCreation: true,
    },
  });

  const handleSubmit = async (values: z.infer<typeof formSchema>) => {
    const code = await onOk(values);
    if (code === 0) {
      form.reset();
    }
  };

  const handleCancel = () => {
    form.reset();
    hideModal();
  };

  return (
    <Dialog open={visible} onOpenChange={handleCancel}>
      <DialogContent className="sm:max-w-[525px]">
        <DialogHeader>
          <DialogTitle>{t('knowledgeDetails.indexLocalFolder')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t('knowledgeDetails.localFolderStorageInfo')}
              </AlertDescription>
            </Alert>
            
            <FormField
              control={form.control}
              name="localPath"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('knowledgeDetails.localFolderPath')}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="/ragflow/mounted_data/your-folder"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    {t('knowledgeDetails.localFolderPathDescription')}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="recursive"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>
                      {t('knowledgeDetails.recursiveScan')}
                    </FormLabel>
                    <FormDescription>
                      {t('knowledgeDetails.recursiveScanDescription')}
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="parseOnCreation"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>
                      {t('knowledgeDetails.parseAfterIndexing')}
                    </FormLabel>
                    <FormDescription>
                      {t('knowledgeDetails.parseAfterIndexingDescription')}
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCancel}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" loading={loading}>
                {t('common.ok')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
