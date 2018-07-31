unit uwizardconfigconsole;

{$mode objfpc}{$H+}

interface

uses

  uwizardconfigconsole_data,

  Classes, SysUtils, Forms, Controls, Graphics, Dialogs, uwizard,
  ComCtrls,ExtCtrls, StdCtrls, PopupNotifier, EditBtn, WizardControls;

type


  { TWizardConfigConsole }

  TWizardConfigConsole = class(TWizard)
    procedure FormClose(Sender: TObject; var CloseAction: TCloseAction);
    procedure FormCreate(Sender: TObject);  override;
    procedure FormShow(Sender: TObject);



  private
    m_data : TWizardConfigConsoleData;


  public
    function data() : Pointer; override; final;


  end;

var
  WizardConfigConsole: TWizardConfigConsole;

implementation

uses
  dmwaptpython,
  uwapt_ini,
  uwizardconfigconsole_server,
  uwizardconfigconsole_welcome,
  uwizardconfigconsole_keyoption,
  uwizardconfigconsole_package_use_existing_key,
  uwizardconfigconsole_package_create_new_key,
  uwizardconfigconsole_buildagent,
  uwizardconfigconsole_restartwaptservice,
  uwizardconfigconsole_finished,
  waptcommon,
  uwizardutil,
  FileUtil;

{$R *.lfm}

{ TWizardConfigConsole }

procedure TWizardConfigConsole.FormCreate(Sender: TObject);
var
  s : String;
  r : integer;

begin
  inherited;

  FillChar( m_data, sizeof(TWizardConfigConsoleData), 0 );

  // Some default settings
  m_data.is_enterprise_edition := DMPython.IsEnterpriseEdition;
  m_data.check_certificates_validity := '0';
  m_data.verify_cert := '0';


  // If no waptservice installed, skip related page
  r := wapt_installpath_waptservice(s);
  if r <> 0 then
    WizardManager.PageByName( PAGE_BUILD_AGENT ).NextOffset := 2;



end;

procedure TWizardConfigConsole.FormShow(Sender: TObject);
begin
    self.WizardButtonPanel.NextButton.SetFocus;
end;

procedure TWizardConfigConsole.FormClose(Sender: TObject; var CloseAction: TCloseAction);
begin
  if m_data.launch_console then
    self.launch_console();
end;

function TWizardConfigConsole.data(): Pointer;
begin
  exit( @m_data );
end;

end.

